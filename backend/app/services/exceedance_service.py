"""超标记录查询与人工标注.

列表 / 导出 / 工作台统计 / 首页待办共用同一份筛选解析 (:func:`exceedance_filters`)
与排序 (:func:`exceedance_query`), 统计汇总直接复用已解析的筛选条件,
保证"工作台列表条数 == summary.total == 导出行数 (上限内)"。
"""
from datetime import datetime

from sqlalchemy import func

from ..domain.constants import EXCEEDANCE_LEVEL_LABELS, EXCEEDANCE_STATUS_LABELS
from ..domain import metrics
from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..models import Exceedance, Station
from ..models.base import iso
from . import filters as qf
from .list_query import apply_ordering

STATUS_CHOICES = tuple(EXCEEDANCE_STATUS_LABELS.keys())
LEVEL_CHOICES = tuple(EXCEEDANCE_LEVEL_LABELS.keys())

# 超标记录的统一字段规格。关键字语义是"监测点名称/编码 + 标注说明",
# 与监测数据查询的关键字语义不同, 因此各自保留谓词, 但解析口径一致。
EXCEEDANCE_FILTER_FIELDS = (
    qf.FilterSpec("statuses", "multi", param="status", choices=STATUS_CHOICES),
    qf.FilterSpec("levels", "multi", param="level", choices=LEVEL_CHOICES),
    qf.FilterSpec("pollutants", "multi", param="pollutant", upper=True),
    qf.FilterSpec("station_ids", "int_multi", param="station_id"),
    qf.FilterSpec("areas", "multi", param="area"),
    qf.FilterSpec("keyword", "text"),
    qf.FilterSpec("date_from", "date_from",
                  check_range=("date_from", "date_to", "开始时间不能晚于结束时间")),
    qf.FilterSpec("date_to", "date_to"),
    qf.FilterSpec("min_ratio", "float"),
    qf.FilterSpec("annotated", "bool"),
)

_SORT_COLUMNS = {
    "measured_at": Exceedance.measured_at,
    "exceed_ratio": Exceedance.exceed_ratio,
    "level": Exceedance.level,
    "updated_at": Exceedance.updated_at,
}


def exceedance_filter_set(args):
    """请求参数 -> 超标记录归一化筛选字典 (列表/统计/导出共用)。"""
    return qf.parse_filter_set(args, EXCEEDANCE_FILTER_FIELDS)


def _apply_exceedance_filters(query, filters):
    query = qf.apply_conditions(query, filters, (
        ("statuses", qf.in_(Exceedance.status)),
        ("levels", qf.in_(Exceedance.level)),
        ("pollutants", qf.in_(Exceedance.pollutant)),
        ("station_ids", qf.in_(Exceedance.station_id)),
        ("areas", qf.in_(Station.area)),
        ("date_from", qf.ge_(Exceedance.measured_at)),
        ("date_to", qf.le_(Exceedance.measured_at)),
        ("min_ratio", qf.ge_(Exceedance.exceed_ratio)),
        ("annotated", lambda value_query, value: value_query.filter(
            Exceedance.annotated_at.isnot(None) if value else Exceedance.annotated_at.is_(None)
        )),
        ("keyword", qf.keyword_any_(Station.name, Station.code, Exceedance.note)),
    ))
    return query


def get_exceedance(exceedance_id):
    exceedance = db.session.get(Exceedance, exceedance_id)
    if exceedance is None:
        raise NotFoundError("超标记录不存在: id=%s" % exceedance_id)
    return exceedance


def ordered_exceedance_query(filters, args=None):
    """在已解析筛选条件上拼装 JOIN/谓词/排序 (列表与导出共用)。"""
    query = db.session.query(Exceedance).join(Station, Exceedance.station_id == Station.id)
    query = _apply_exceedance_filters(query, filters)
    return apply_ordering(
        query, args or {}, _SORT_COLUMNS,
        default_sort="measured_at", default_order="desc",
        tie_breaker=Exceedance.id.desc(),
    )


def exceedance_query(args):
    """超标记录完整查询 (列表/导出/统计/首页待办共用)。"""
    filters = exceedance_filter_set(args)
    return ordered_exceedance_query(filters, args)


def annotate(exceedance, status=None, note=None, annotator=None, level=None):
    """Apply a manual annotation to an exceedance record."""
    if status is not None:
        if status not in STATUS_CHOICES:
            raise ValidationError(
                "标注状态取值不合法, 可选: %s" % ", ".join(STATUS_CHOICES),
                fields={"status": "unknown"},
            )
        exceedance.status = status
    if level is not None:
        if level not in LEVEL_CHOICES:
            raise ValidationError(
                "超标等级取值不合法, 可选: %s" % ", ".join(LEVEL_CHOICES),
                fields={"level": "unknown"},
            )
        exceedance.level = level

    note = (note or "").strip()
    if exceedance.status == "pending":
        exceedance.note = note or exceedance.note
        exceedance.annotator = annotator or exceedance.annotator
        exceedance.annotated_at = None if not note else datetime.now()
    else:
        if not note:
            reason = "确认" if exceedance.status == "confirmed" else "忽略"
            raise ValidationError(
                "标注为\"%s\"时必须填写%s原因" % (EXCEEDANCE_STATUS_LABELS[exceedance.status], reason),
                fields={"note": "required"},
            )
        exceedance.note = note
        exceedance.annotator = annotator or "未署名"
        exceedance.annotated_at = datetime.now()

    db.session.commit()
    return exceedance


def annotate_batch(ids, status, note=None, annotator=None, level=None):
    """Batch annotation used by the exceedance work bench."""
    ids = list(dict.fromkeys(int(item) for item in ids))
    if not ids:
        raise ValidationError("请至少选择一条超标记录", fields={"ids": "empty"})

    records = Exceedance.query.filter(Exceedance.id.in_(ids)).all()
    found = {record.id for record in records}
    missing = [item for item in ids if item not in found]

    updated = []
    for record in records:
        annotate_silent = {
            "status": status if status is not None else record.status,
            "level": level if level is not None else record.level,
            "note": note,
            "annotator": annotator,
        }
        if annotate_silent["status"] != "pending" and not (note or "").strip():
            raise ValidationError(
                "批量标注为\"%s\"时必须填写标注说明"
                % EXCEEDANCE_STATUS_LABELS.get(annotate_silent["status"], annotate_silent["status"]),
                fields={"note": "required"},
            )
        record.status = annotate_silent["status"]
        record.level = annotate_silent["level"]
        if (note or "").strip():
            record.note = note.strip()
        if annotate_silent["status"] == "pending":
            record.annotated_at = None
        else:
            record.annotator = annotator or record.annotator or "未署名"
            record.annotated_at = datetime.now()
        updated.append(record.id)

    db.session.commit()
    return {"updated": len(updated), "updated_ids": updated, "missing": missing}


def _filtered_subquery(filters):
    """筛选后的超标记录子查询, 供各项分组统计共用同一口径。"""
    base = _apply_exceedance_filters(
        db.session.query(
            Exceedance.id, Exceedance.station_id,
            Exceedance.status, Exceedance.level,
            Exceedance.pollutant, Exceedance.exceed_ratio,
        ).join(Station, Exceedance.station_id == Station.id),
        filters,
    )
    return base.subquery()


def summary(args):
    """Dashboard counters for the annotation work bench.

    ``args`` 可以是原始请求参数, 也可以是已经解析过的归一化筛选字典,
    避免列表接口里对同一批参数解析两次。
    """
    filters = _as_filters(args)
    subquery = _filtered_subquery(filters)

    by_status = {
        status: {"key": status, "label": label, "count": 0}
        for status, label in EXCEEDANCE_STATUS_LABELS.items()
    }
    for status, count in (
        db.session.query(subquery.c.status, func.count()).group_by(subquery.c.status).all()
    ):
        if status in by_status:
            by_status[status]["count"] = int(count)

    by_level = {
        level: {"key": level, "label": label, "count": 0}
        for level, label in EXCEEDANCE_LEVEL_LABELS.items()
    }
    for level, count in (
        db.session.query(subquery.c.level, func.count()).group_by(subquery.c.level).all()
    ):
        if level in by_level:
            by_level[level]["count"] = int(count)

    top_pollutants = [
        {"key": pollutant, "count": int(count), "avg_ratio": metrics.ratio3(avg_ratio)}
        for pollutant, count, avg_ratio in (
            db.session.query(
                subquery.c.pollutant,
                func.count(),
                func.avg(subquery.c.exceed_ratio),
            )
            .group_by(subquery.c.pollutant)
            .order_by(func.count().desc())
            .all()
        )
    ]

    top_stations = [
        {"station_id": station_id, "station_name": name, "count": int(count)}
        for station_id, name, count in (
            db.session.query(
                subquery.c.station_id,
                Station.name,
                func.count(),
            )
            .join(Station, Station.id == subquery.c.station_id)
            .group_by(subquery.c.station_id, Station.name)
            .order_by(func.count().desc())
            .limit(5)
            .all()
        )
    ]

    totals = db.session.query(
        func.count(subquery.c.id),
        func.max(subquery.c.exceed_ratio),
        func.avg(subquery.c.exceed_ratio),
    ).one()

    return {
        "total": int(totals[0] or 0),
        "pending": by_status["pending"]["count"],
        "by_status": list(by_status.values()),
        "by_level": list(by_level.values()),
        "top_pollutants": top_pollutants,
        "top_stations": top_stations,
        "max_ratio": metrics.ratio3(totals[1] or 0),
        "avg_ratio": metrics.ratio3(totals[2] or 0),
        "generated_at": iso(datetime.now()),
    }


def _as_filters(args):
    """接受原始参数或已归一化的筛选字典, 归一化结果含本模块的全部键。"""
    if isinstance(args, dict) and "statuses" in args:
        return args
    return exceedance_filter_set(args)
