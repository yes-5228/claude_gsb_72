"""监测数据查询: 过滤条件解析, 统计聚合与导出数据准备.

本模块是"监测数据"这一实体的**唯一查询口径**:

- 筛选解析 (:func:`measurement_filter_set` / :func:`parse_filters`)
- SQL 谓词拼装 (:func:`apply_filters`)
- 排序 (:func:`measurement_query`, 与列表/导出共用)
- 汇总与分组聚合 (:func:`summary` / :func:`statistics`)

``/api/measurements``、``/api/query/*``、``/api/meta/overview`` 以及 CSV 导出
都只允许调用这里的函数, 保证同一条件下条数、顺序、汇总完全一致。
"""
from sqlalchemy import cast, func

from ..domain.constants import (
    DATA_SOURCE_LABELS,
    EXCEEDANCE_STATUS_LABELS,
    PERIOD_LABELS,
    STATION_TYPE_LABELS,
)
from ..domain import metrics
from ..domain.standards import POLLUTANT_CODES, get_pollutant
from ..errors import ValidationError
from ..extensions import db
from ..models import Exceedance, Measurement, Station
from ..models.base import iso
from . import filters as qf
from .list_query import apply_ordering

GROUP_BY_CHOICES = ("station", "area", "pollutant", "period", "day", "month", "data_source")
METRIC_CHOICES = ("avg", "max", "min", "count", "sum")
SORT_CHOICES = ("measured_at", "value", "exceed_ratio", "pollutant", "station_code", "created_at")

# 监测数据的统一字段规格; measurements 列表与 query 高级检索共用这一份。
MEASUREMENT_FILTER_FIELDS = (
    qf.FilterSpec("station_ids", "int_multi", param="station_id"),
    qf.FilterSpec("areas", "multi", param="area"),
    qf.FilterSpec("station_types", "multi", param="station_type",
                  choices=tuple(STATION_TYPE_LABELS.keys())),
    qf.FilterSpec("pollutants", "multi", param="pollutant",
                  choices=POLLUTANT_CODES, upper=True),
    qf.FilterSpec("periods", "multi", param="period", choices=tuple(PERIOD_LABELS.keys())),
    qf.FilterSpec("data_sources", "multi", param="data_source",
                  choices=tuple(DATA_SOURCE_LABELS.keys())),
    qf.FilterSpec("is_exceeded", "bool"),
    qf.FilterSpec("exceedance_status", "multi",
                  choices=tuple(EXCEEDANCE_STATUS_LABELS.keys())),
    qf.FilterSpec("date_from", "date_from",
                  check_range=("date_from", "date_to", "开始时间不能晚于结束时间")),
    qf.FilterSpec("date_to", "date_to"),
    qf.FilterSpec("min_value", "float",
                  check_range=("min_value", "max_value", "最小值不能大于最大值")),
    qf.FilterSpec("max_value", "float"),
    qf.FilterSpec("keyword", "text"),
    qf.FilterSpec("recorder", "text"),
)

_SORT_COLUMNS = {
    "measured_at": Measurement.measured_at,
    "value": Measurement.value,
    "exceed_ratio": Measurement.exceed_ratio,
    "pollutant": Measurement.pollutant,
    "station_code": Station.code,
    "created_at": Measurement.created_at,
}


def measurement_filter_set(args):
    """请求参数 -> 监测数据归一化筛选字典 (唯一入口)。"""
    return qf.parse_filter_set(args, MEASUREMENT_FILTER_FIELDS)


# 向后兼容的旧函数名, 供其他服务/脚本调用。
parse_filters = measurement_filter_set


def apply_filters(query, filters):
    """归一化筛选字典 -> SQLAlchemy WHERE/JOIN 谓词 (唯一实现)。"""
    query = query.join(Station, Measurement.station_id == Station.id)

    query = qf.apply_conditions(query, filters, (
        ("station_ids", qf.in_(Measurement.station_id)),
        ("areas", qf.in_(Station.area)),
        ("station_types", qf.in_(Station.station_type)),
        ("pollutants", qf.in_(Measurement.pollutant)),
        ("periods", qf.in_(Measurement.period)),
        ("data_sources", qf.in_(Measurement.data_source)),
        ("is_exceeded", qf.equal_(Measurement.is_exceeded)),
        ("date_from", qf.ge_(Measurement.measured_at)),
        ("date_to", qf.le_(Measurement.measured_at)),
        ("min_value", qf.ge_(Measurement.value)),
        ("max_value", qf.le_(Measurement.value)),
        ("recorder", qf.like_(Measurement.recorder)),
        ("keyword", qf.keyword_any_(Station.name, Station.code, Station.address)),
    ))

    # 标注状态过滤需要 JOIN 超标记录; measurement_id 在 exceedances 上唯一,
    # JOIN 不会放大行数, 因此列表条数与 summary 始终一致。
    if filters["exceedance_status"]:
        query = query.join(Exceedance, Exceedance.measurement_id == Measurement.id).filter(
            Exceedance.status.in_(filters["exceedance_status"])
        )
    return query


def apply_sort(query, sort=None, order="desc"):
    """排序规则 (列表与导出共用, id 降序兜底)。"""
    args = {}
    if sort is not None:
        args["sort"] = sort
    if order is not None:
        args["order"] = order
    return apply_ordering(
        query, args, _SORT_COLUMNS,
        default_sort="measured_at", default_order="desc",
        tie_breaker=Measurement.id.desc(),
    )


def measurement_query(args):
    """完整监测数据查询: 解析 -> 谓词 -> 排序。所有列表/导出入口共用。"""
    filters = measurement_filter_set(args)
    query = apply_filters(db.session.query(Measurement), filters)
    return apply_sort(query, args.get("sort"), args.get("order")), filters


def summary(filters):
    """筛选范围内的汇总计数 (查询页 / 录入页 / 概览页共用同一份)。"""
    query = apply_filters(
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
        "exceed_rate": metrics.ratio(exceeded, total),
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "avg_value": metrics.rounded(avg_value),
    }


def _metric_expression(metric):
    return {
        "avg": func.avg(Measurement.value),
        "max": func.max(Measurement.value),
        "min": func.min(Measurement.value),
        "count": func.count(Measurement.id),
        "sum": func.sum(Measurement.value),
    }[metric]


def statistics(args):
    """分组聚合 (查询页统计面板与概览页近 7 日趋势共用)。"""
    filters = measurement_filter_set(args)
    group_by = args.get("group_by") or "pollutant"
    metric = args.get("metric") or "avg"
    if group_by not in GROUP_BY_CHOICES:
        raise ValidationError(
            "group_by 仅支持: %s" % ", ".join(GROUP_BY_CHOICES), fields={"group_by": "unknown"}
        )
    if metric not in METRIC_CHOICES:
        raise ValidationError(
            "metric 仅支持: %s" % ", ".join(METRIC_CHOICES), fields={"metric": "unknown"}
        )

    value_expr = _metric_expression(metric).label("metric_value")
    count_expr = func.count(Measurement.id).label("row_count")
    exceeded_expr = func.sum(cast(Measurement.is_exceeded, db.Integer)).label("exceeded_count")

    if group_by == "station":
        query = db.session.query(
            Station.id.label("station_id"),
            Station.code.label("station_code"),
            Station.name.label("station_name"),
            Station.area.label("area"),
            value_expr,
            count_expr,
            exceeded_expr,
        ).group_by(Station.id, Station.code, Station.name, Station.area)
        is_time_group = False
    elif group_by == "area":
        query = db.session.query(
            Station.area.label("area"), value_expr, count_expr, exceeded_expr
        ).group_by(Station.area)
        is_time_group = False
    elif group_by == "day":
        bucket = func.date(Measurement.measured_at).label("bucket")
        query = db.session.query(bucket, value_expr, count_expr, exceeded_expr).group_by(bucket)
        is_time_group = True
    elif group_by == "month":
        year = func.extract("year", Measurement.measured_at).label("year")
        month = func.extract("month", Measurement.measured_at).label("month")
        query = db.session.query(year, month, value_expr, count_expr, exceeded_expr).group_by(
            year, month
        )
        is_time_group = True
    else:
        column = {
            "pollutant": Measurement.pollutant,
            "period": Measurement.period,
            "data_source": Measurement.data_source,
        }[group_by]
        query = db.session.query(
            column.label("bucket"), value_expr, count_expr, exceeded_expr
        ).group_by(column)
        is_time_group = False

    query = apply_filters(query, filters)
    rows = query.all()

    items = []
    for row in rows:
        data = dict(row._mapping)
        count = int(data.get("row_count") or 0)
        exceeded = int(data.get("exceeded_count") or 0)
        raw_value = data.get("metric_value")
        if group_by == "station":
            key = data.get("station_code")
            label = "%s %s" % (data.get("station_code"), data.get("station_name"))
        elif group_by == "area":
            key = label = data.get("area")
        elif group_by == "day":
            key = str(data.get("bucket"))
            label = key
        elif group_by == "month":
            key = "%04d-%02d" % (int(data.get("year")), int(data.get("month")))
            label = key
        elif group_by == "pollutant":
            key = data.get("bucket")
            meta = get_pollutant(key)
            label = meta["label"] if meta else key
        elif group_by == "period":
            key = data.get("bucket")
            label = PERIOD_LABELS.get(key, key)
        else:
            key = data.get("bucket")
            label = DATA_SOURCE_LABELS.get(key, key)

        items.append(
            {
                "key": key,
                "label": label,
                "value": metrics.rounded(raw_value),
                "count": count,
                "exceeded_count": exceeded,
                "exceed_rate": metrics.ratio(exceeded, count),
            }
        )

    if is_time_group:
        items.sort(key=lambda item: item["key"])
    else:
        items.sort(key=lambda item: (item["value"] is None, -(item["value"] or 0)))

    return {
        "group_by": group_by,
        "metric": metric,
        "items": items,
        "totals": {
            "count": sum(item["count"] for item in items),
            "exceeded_count": sum(item["exceeded_count"] for item in items),
        },
    }


def option_payload():
    return {
        "group_by": list(GROUP_BY_CHOICES),
        "metric": list(METRIC_CHOICES),
        "sort": list(SORT_CHOICES),
        "exceedance_status": [
            {"value": key, "label": label} for key, label in EXCEEDANCE_STATUS_LABELS.items()
        ],
        "station_type": [
            {"value": key, "label": label} for key, label in STATION_TYPE_LABELS.items()
        ],
    }
