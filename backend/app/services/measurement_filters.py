"""监测数据(Measurement)的统一查询口径.

监测数据在系统中有四个消费入口:

1. ``GET /api/measurements``        录入页列表
2. ``GET /api/measurements/export`` 录入页导出
3. ``GET /api/query/measurements``  查询页列表 + ``/query/statistics`` 聚合
4. ``GET /api/query/export``        查询页导出
   (另外 ``/api/meta/overview`` 的概览统计也复用同一解析器)

以上入口对同一份请求参数必须得到:
- 同一批命中行 (``build_measurement_query`` 单一构造点);
- 同一默认顺序 (监测时间倒序, 同时间按 id 倒序兜底);
- 同一汇总口径 (``measurement_summary``)。

``parse_measurement_filters`` 返回规整化后的筛选字典,
键名同时作为列表接口响应中的 ``applied_filters`` 字段, 不得改名。
"""
from sqlalchemy import cast, func, or_

from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS, STATION_TYPE_LABELS
from ..domain.metrics import exceed_rate, round2
from ..domain.standards import POLLUTANT_CODES
from ..errors import ValidationError
from ..extensions import db
from ..models import Exceedance, Measurement, Station
from ..models.base import iso
from ..utils import filter_args as fa

SORT_CHOICES = ("measured_at", "value", "exceed_ratio", "pollutant", "station_code", "created_at")

SORT_COLUMNS = {
    "measured_at": Measurement.measured_at,
    "value": Measurement.value,
    "exceed_ratio": Measurement.exceed_ratio,
    "pollutant": Measurement.pollutant,
    "station_code": Station.code,
    "created_at": Measurement.created_at,
}


def parse_measurement_filters(args):
    """把请求参数解析为规整化筛选字典 (四入口共用)."""
    pollutants = [item.upper() for item in fa.multi_str(args, "pollutant")]
    unknown = [item for item in pollutants if item not in POLLUTANT_CODES]
    if unknown:
        raise ValidationError(
            "未知监测因子: %s" % ", ".join(unknown), fields={"pollutant": "unknown"}
        )

    periods = fa.multi_str(args, "period")
    bad_periods = [item for item in periods if item not in PERIOD_LABELS]
    if bad_periods:
        raise ValidationError(
            "未知数据周期: %s" % ", ".join(bad_periods), fields={"period": "unknown"}
        )

    filters = {
        "station_ids": fa.multi_int(args, "station_id"),
        "areas": fa.multi_str(args, "area"),
        "station_types": fa.choice_list(args, "station_type", tuple(STATION_TYPE_LABELS)),
        "pollutants": pollutants,
        "periods": periods,
        "data_sources": fa.choice_list(args, "data_source", tuple(DATA_SOURCE_LABELS)),
        "is_exceeded": fa.tri_bool(args, "is_exceeded"),
        "exceedance_status": fa.choice_list(
            args, "exceedance_status", ("pending", "confirmed", "ignored")
        ),
        "date_from": fa.date_bound(args, "date_from"),
        "date_to": fa.date_bound(args, "date_to", end_of_day=True),
        "min_value": fa.single_float(args, "min_value"),
        "max_value": fa.single_float(args, "max_value"),
        "keyword": fa.text_arg(args, "keyword"),
        "recorder": fa.text_arg(args, "recorder"),
    }
    fa.require_ordered_range(
        filters["date_from"], filters["date_to"], "date_from", "开始时间不能晚于结束时间"
    )
    fa.require_ordered_range(
        filters["min_value"], filters["max_value"], "min_value", "最小值不能大于最大值"
    )
    return filters


def apply_measurement_filters(query, filters):
    """在任意以 Measurement 为主体的查询上叠加筛选 (列表/计数/聚合都可用)."""
    query = query.join(Station, Measurement.station_id == Station.id)
    if filters["station_ids"]:
        query = query.filter(Measurement.station_id.in_(filters["station_ids"]))
    if filters["areas"]:
        query = query.filter(Station.area.in_(filters["areas"]))
    if filters["station_types"]:
        query = query.filter(Station.station_type.in_(filters["station_types"]))
    if filters["pollutants"]:
        query = query.filter(Measurement.pollutant.in_(filters["pollutants"]))
    if filters["periods"]:
        query = query.filter(Measurement.period.in_(filters["periods"]))
    if filters["data_sources"]:
        query = query.filter(Measurement.data_source.in_(filters["data_sources"]))
    if filters["is_exceeded"] is not None:
        query = query.filter(Measurement.is_exceeded.is_(filters["is_exceeded"]))
    if filters["date_from"]:
        query = query.filter(Measurement.measured_at >= filters["date_from"])
    if filters["date_to"]:
        query = query.filter(Measurement.measured_at <= filters["date_to"])
    if filters["min_value"] is not None:
        query = query.filter(Measurement.value >= filters["min_value"])
    if filters["max_value"] is not None:
        query = query.filter(Measurement.value <= filters["max_value"])
    if filters["recorder"]:
        query = query.filter(Measurement.recorder.like("%" + filters["recorder"] + "%"))
    if filters["keyword"]:
        like = "%" + filters["keyword"] + "%"
        query = query.filter(
            or_(Station.name.like(like), Station.code.like(like), Station.address.like(like))
        )
    if filters["exceedance_status"]:
        # 关系为一对一, inner join 不会放大行数
        query = query.join(Exceedance, Exceedance.measurement_id == Measurement.id).filter(
            Exceedance.status.in_(filters["exceedance_status"])
        )
    return query


def apply_measurement_sort(query, sort=None, order="desc"):
    """统一排序: 未知排序字段回退监测时间; 同值时以 id 倒序作为稳定兜底."""
    sort = sort if sort in SORT_CHOICES else "measured_at"
    column = SORT_COLUMNS[sort]
    primary = column.desc() if (order or "desc").lower() == "desc" else column.asc()
    return query.order_by(primary, Measurement.id.desc())


def build_measurement_query(args):
    """解析 + 过滤 + 排序, 返回 (排序后查询, 规整化筛选). 四个入口共用."""
    filters = parse_measurement_filters(args)
    query = apply_measurement_filters(db.session.query(Measurement), filters)
    return apply_measurement_sort(query, args.get("sort"), args.get("order")), filters


def measurement_summary(filters):
    """当前筛选范围下的统一汇总卡数据 (列表、概览共用)."""
    query = apply_measurement_filters(
        db.session.query(
            func.count(Measurement.id),
            func.sum(cast(Measurement.is_exceeded, db.Integer)),
            func.count(func.distinct(Measurement.station_id)),
            func.min(Measurement.measured_at),
            func.max(Measurement.measured_at),
            func.avg(Measurement.value),
        ),
        filters,
    )
    total, exceeded, stations, first_at, last_at, avg_value = query.one()
    total = int(total or 0)
    exceeded = int(exceeded or 0)
    return {
        "total": total,
        "exceeded_count": exceeded,
        "exceed_rate": exceed_rate(exceeded, total),
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "avg_value": round2(avg_value),
    }
