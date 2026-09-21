"""超标记录(Exceedance)的统一查询口径.

超标工作台列表、筛选统计、导出与概览页待办共用同一构造点,
保证同参数下命中条数、顺序与统计完全一致。

超标记录是监测数据的派生数据: 正常路径下每一条都由录入时的
``domain.exceedance_rules.evaluate`` 判定生成, 本模块只负责查询,
不允许出现第二套 "是否超标 / 如何分级" 的规则。
"""
from sqlalchemy import or_

from ..domain.constants import EXCEEDANCE_LEVEL_LABELS, EXCEEDANCE_STATUS_LABELS
from ..domain.standards import POLLUTANT_CODES
from ..errors import ValidationError
from ..extensions import db
from ..models import Exceedance, Station
from ..utils import filter_args as fa

SORT_CHOICES = ("measured_at", "exceed_ratio", "level", "updated_at")
SORT_COLUMNS = {
    "measured_at": Exceedance.measured_at,
    "exceed_ratio": Exceedance.exceed_ratio,
    "level": Exceedance.level,
    "updated_at": Exceedance.updated_at,
}


def parse_exceedance_filters(args):
    """解析超标记录查询参数, 未知枚举统一按 422 处理 (与监测数据查询对齐)."""
    pollutants = [item.upper() for item in fa.multi_str(args, "pollutant")]
    unknown = [item for item in pollutants if item not in POLLUTANT_CODES]
    if unknown:
        raise ValidationError(
            "未知监测因子: %s" % ", ".join(unknown), fields={"pollutant": "unknown"}
        )

    filters = {
        "statuses": fa.choice_list(args, "status", tuple(EXCEEDANCE_STATUS_LABELS)),
        "levels": fa.choice_list(args, "level", tuple(EXCEEDANCE_LEVEL_LABELS)),
        "pollutants": pollutants,
        "station_ids": fa.multi_int(args, "station_id"),
        "areas": fa.multi_str(args, "area"),
        "keyword": fa.text_arg(args, "keyword"),
        "date_from": fa.date_bound(args, "date_from"),
        "date_to": fa.date_bound(args, "date_to", end_of_day=True),
        "min_ratio": fa.single_float(args, "min_ratio"),
        "annotated": fa.tri_bool(args, "annotated"),
    }
    fa.require_ordered_range(
        filters["date_from"], filters["date_to"], "date_from", "开始时间不能晚于结束时间"
    )
    return filters


def apply_exceedance_filters(query, filters):
    query = query.join(Station, Exceedance.station_id == Station.id)
    if filters["statuses"]:
        query = query.filter(Exceedance.status.in_(filters["statuses"]))
    if filters["levels"]:
        query = query.filter(Exceedance.level.in_(filters["levels"]))
    if filters["pollutants"]:
        query = query.filter(Exceedance.pollutant.in_(filters["pollutants"]))
    if filters["station_ids"]:
        query = query.filter(Exceedance.station_id.in_(filters["station_ids"]))
    if filters["areas"]:
        query = query.filter(Station.area.in_(filters["areas"]))
    if filters["keyword"]:
        like = "%" + filters["keyword"] + "%"
        query = query.filter(
            or_(Station.name.like(like), Station.code.like(like), Exceedance.note.like(like))
        )
    if filters["date_from"]:
        query = query.filter(Exceedance.measured_at >= filters["date_from"])
    if filters["date_to"]:
        query = query.filter(Exceedance.measured_at <= filters["date_to"])
    if filters["min_ratio"] is not None:
        query = query.filter(Exceedance.exceed_ratio >= filters["min_ratio"])
    if filters["annotated"] is True:
        query = query.filter(Exceedance.annotated_at.isnot(None))
    elif filters["annotated"] is False:
        query = query.filter(Exceedance.annotated_at.is_(None))
    return query


def apply_exceedance_sort(query, sort=None, order="desc"):
    sort = sort if sort in SORT_CHOICES else "measured_at"
    column = SORT_COLUMNS[sort]
    primary = column.desc() if (order or "desc").lower() == "desc" else column.asc()
    return query.order_by(primary, Exceedance.id.desc())


def build_exceedance_query(args):
    """解析 + 过滤 + 排序, 返回 (排序后查询, 规整化筛选)."""
    filters = parse_exceedance_filters(args)
    query = apply_exceedance_filters(db.session.query(Exceedance), filters)
    return apply_exceedance_sort(query, args.get("sort"), args.get("order")), filters
