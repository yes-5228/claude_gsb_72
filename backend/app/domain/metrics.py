"""统一统计口径: 达标率 / 超标率 / 四舍五入精度。

所有入口 (查询汇总、分组聚合、超标工作台、台账详情、首页概览) 都必须使用
这里的函数, 不允许各处再写一份 ``a / b``。

口径定义:

- ``exceed_rate`` = 超标条数 / 参与判定的总条数; 分母为 0 时取 0.0;
- 比率统一保留 4 位小数 (前端以百分比展示时为两位小数);
- 浓度均值保留 2 位小数; 超标倍数相关保留 3 位小数;
- 分母为 0 属于"无数据", 用 0.0 而不是 None, 保证各入口展示与导出一致。
"""

RATE_DIGITS = 4
VALUE_DIGITS = 2
RATIO_DIGITS = 3


def ratio(numerator, denominator, digits=RATE_DIGITS):
    """超标率/达标率等比率的唯一算法: 分母为 0 时返回 0.0。"""
    denominator = int(denominator or 0)
    if denominator <= 0:
        return 0.0
    return round(int(numerator or 0) / denominator, digits)


def rounded(value, digits=VALUE_DIGITS):
    """浓度类聚合值: None 保持 None (区分"无数据"与 0)。"""
    return round(float(value), digits) if value is not None else None


def ratio3(value):
    """超标倍数类展示精度 (3 位)。"""
    return round(float(value), RATIO_DIGITS) if value is not None else None
