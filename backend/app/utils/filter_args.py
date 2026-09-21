"""统一的查询字符串解析原语.

所有列表 / 统计 / 导出 / 概览入口共用同一套多值、数值、布尔与日期口径,
入参既支持 Flask 的 ``request.args``, 也支持服务内部构造的普通 dict
(例如概览页组装的筛选条件)。
"""
from datetime import datetime, time

from ..errors import ValidationError
from .validation import parse_date

TRUTHY_TOKENS = {"1", "true", "yes", "on"}
FALSY_TOKENS = {"0", "false", "no", "off"}


def multi_str(args, name):
    """逗号分隔的多值字符串参数: 去空白、去空项, 缺省返回 []."""
    raw = args.get(name)
    if not raw:
        return []
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def multi_int(args, name):
    """逗号分隔的多值整数参数, 任一项非整数统一按 422 处理."""
    values = []
    for item in multi_str(args, name):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError(
                "%s 参数必须为整数" % name, fields={name: "invalid_integer"}
            )
    return values


def single_float(args, name):
    """单个浮点参数; 缺省/空串返回 None, 非法数字统一按 422 处理."""
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "%s 参数必须为数字" % name, fields={name: "invalid_number"}
        )


def tri_bool(args, name):
    """三态布尔: 真值 token -> True, 假值 token -> False, 缺省/无法识别 -> None(不过滤)."""
    raw = args.get(name)
    if raw in (None, ""):
        return None
    token = str(raw).strip().lower()
    if token in TRUTHY_TOKENS:
        return True
    if token in FALSY_TOKENS:
        return False
    return None


def date_bound(args, name, end_of_day=False):
    """日期边界: 开始日按 00:00:00, 结束日按 23:59:59.999999 (含当日全天)."""
    raw = args.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, name)
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def text_arg(args, name):
    """去空白的单值文本参数."""
    return (args.get(name) or "").strip()


def choice_list(args, name, choices):
    """多值枚举参数: 逐项校验白名单, 出现未知取值统一按 422 处理."""
    values = multi_str(args, name)
    unknown = [item for item in values if item not in choices]
    if unknown:
        raise ValidationError(
            "%s 包含未知取值: %s" % (name, ", ".join(unknown)),
            fields={name: "unknown"},
        )
    return values


def require_ordered_range(low, high, field, message):
    """区间参数下限不得大于上限."""
    if low is not None and high is not None and low > high:
        raise ValidationError(message, fields={field: "range_invalid"})
