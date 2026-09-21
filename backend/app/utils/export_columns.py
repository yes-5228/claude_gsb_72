"""统一的 CSV 导出列定义与取数口径.

三处导出 (录入页监测数据、查询页监测数据、超标工作台) 的列定义集中在此,
保证同一行数据在任何入口导出的表头、取值、中文/代码口径完全一致。
监测数据两个入口共用同一基础列, 录入页导出额外追加 "备注" 列。
"""
from flask import current_app

from ..domain.constants import (
    DATA_SOURCE_LABELS,
    EXCEEDANCE_LEVEL_LABELS,
    EXCEEDANCE_STATUS_LABELS,
    PERIOD_LABELS,
)
from .csv_export import csv_response


def _yes_no(value):
    return "是" if value else "否"


def _period_label(row):
    return PERIOD_LABELS.get(row.period, row.period)


def _data_source_label(row):
    return DATA_SOURCE_LABELS.get(row.data_source, row.data_source)


def _measured_at_text(row):
    return row.measured_at.strftime("%Y-%m-%d %H:%M")


# 监测数据基础列: 录入页导出与查询页导出必须完全一致
MEASUREMENT_BASE_COLUMNS = [
    ("站点编码", lambda row: row.station.code if row.station else ""),
    ("站点名称", lambda row: row.station.name if row.station else ""),
    ("所属区域", lambda row: row.station.area if row.station else ""),
    ("监测因子", lambda row: row.pollutant_label()),
    ("数据周期", _period_label),
    ("监测值", "value"),
    ("单位", "unit"),
    ("限值", "limit_value"),
    ("是否超标", lambda row: _yes_no(row.is_exceeded)),
    ("超标倍数", "exceed_ratio"),
    ("监测时间", _measured_at_text),
    ("数据来源", _data_source_label),
    ("录入人", "recorder"),
]

# 录入页导出在末尾追加备注 (历史列顺序保持不变)
MEASUREMENT_COLUMNS = MEASUREMENT_BASE_COLUMNS + [("备注", "remark")]

EXCEEDANCE_COLUMNS = [
    ("站点编码", lambda row: row.station.code if row.station else ""),
    ("站点名称", lambda row: row.station.name if row.station else ""),
    ("监测因子", "pollutant"),
    ("监测值", "value"),
    ("限值", "limit_value"),
    ("超标倍数", "exceed_ratio"),
    ("超标等级", lambda row: EXCEEDANCE_LEVEL_LABELS.get(row.level, row.level)),
    ("标注状态", lambda row: EXCEEDANCE_STATUS_LABELS.get(row.status, row.status)),
    ("监测时间", _measured_at_text),
    ("标注说明", "note"),
    ("标注人", "annotator"),
    ("标注时间", lambda row: row.annotated_at.strftime("%Y-%m-%d %H:%M")
        if row.annotated_at else ""),
]


def export_rows(query, limit=None):
    """统一的导出行上限: 默认取配置 MAX_EXPORT_ROWS."""
    limit = current_app.config["MAX_EXPORT_ROWS"] if limit is None else limit
    return query.limit(limit).all()


def csv_export(query, columns, filename_prefix, limit=None):
    """按统一上限取数并生成 CSV 响应."""
    rows = export_rows(query, limit)
    return csv_response(rows, columns, filename_prefix)
