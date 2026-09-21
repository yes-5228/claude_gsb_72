"""统一的 CSV 导出列定义。

同一实体在任何入口导出, 列顺序、表头文案、单元格取值规则必须完全一致,
因此监测数据的两份导出 (录入页 / 高级查询页) 共用这里的列定义;
差异仅在"备注"列 (录入页导出多一列, 保持既有文件内容不变)。
"""
from ..domain.constants import (
    DATA_SOURCE_LABELS,
    EXCEEDANCE_LEVEL_LABELS,
    EXCEEDANCE_STATUS_LABELS,
    PERIOD_LABELS,
)

_MEASUREMENT_TIME = lambda row: row.measured_at.strftime("%Y-%m-%d %H:%M")

# 监测数据导出的公共列 (录入页与查询页一致)。
MEASUREMENT_EXPORT_COLUMNS = [
    ("站点编码", lambda row: row.station.code if row.station else ""),
    ("站点名称", lambda row: row.station.name if row.station else ""),
    ("所属区域", lambda row: row.station.area if row.station else ""),
    ("监测因子", lambda row: row.pollutant_label()),
    ("数据周期", lambda row: PERIOD_LABELS.get(row.period, row.period)),
    ("监测值", "value"),
    ("单位", "unit"),
    ("限值", "limit_value"),
    ("是否超标", lambda row: "是" if row.is_exceeded else "否"),
    ("超标倍数", "exceed_ratio"),
    ("监测时间", _MEASUREMENT_TIME),
    ("数据来源", lambda row: DATA_SOURCE_LABELS.get(row.data_source, row.data_source)),
    ("录入人", "recorder"),
]

# 录入页导出在公共列之后追加"备注", 保持历史导出文件结构不变。
MEASUREMENT_EXPORT_WITH_REMARK_COLUMNS = MEASUREMENT_EXPORT_COLUMNS + [("备注", "remark")]

EXCEEDANCE_EXPORT_COLUMNS = [
    ("站点编码", lambda row: row.station.code if row.station else ""),
    ("站点名称", lambda row: row.station.name if row.station else ""),
    ("监测因子", "pollutant"),
    ("监测值", "value"),
    ("限值", "limit_value"),
    ("超标倍数", "exceed_ratio"),
    ("超标等级", lambda row: EXCEEDANCE_LEVEL_LABELS.get(row.level, row.level)),
    ("标注状态", lambda row: EXCEEDANCE_STATUS_LABELS.get(row.status, row.status)),
    ("监测时间", _MEASUREMENT_TIME),
    ("标注说明", "note"),
    ("标注人", "annotator"),
    ("标注时间", lambda row: row.annotated_at.strftime("%Y-%m-%d %H:%M")
        if row.annotated_at else ""),
]
