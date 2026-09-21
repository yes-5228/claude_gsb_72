"""统一的统计指标计算口径.

列表汇总卡、聚合统计、首页概览、超标工作台统计共用同一套舍入与比率算法,
避免 "同一批数据在不同入口算出不同率值"。
"""


def round2(value):
    """平均浓度等普通指标保留 2 位小数."""
    return round(float(value), 2) if value is not None else None


def round3(value):
    """超标倍数类指标保留 3 位小数 (与录入时 evaluate 的倍数精度一致)."""
    return round(float(value), 3) if value is not None else None


def exceed_rate(exceeded, total):
    """超标率 = 超标条数 / 总条数, 保留 4 位小数; 无数据时为 0.0.

    各入口都必须使用该函数, 不允许各写一份分母为 0 的判断。
    """
    exceeded = int(exceeded or 0)
    total = int(total or 0)
    return round(exceeded / total, 4) if total else 0.0
