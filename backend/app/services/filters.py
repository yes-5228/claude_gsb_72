"""统一查询口径: 多值条件 / 日期范围 / 数值区间的解析与校验.

所有列表入口 (监测数据、超标记录、台账、聚合统计、导出、首页概览) 都必须通过
:func:`parse_filter_set` 把请求参数解析成同一个归一化结构, 再交给
:func:`apply_filter_set` 生成 WHERE 条件, 保证"同一条件 -> 同一 SQL 谓词"。

设计约定 (任何入口都不得另写一份):

- 多值参数统一使用英文逗号分隔, 解析顺序保持调用方传入顺序, 去空白、去空段;
- 整型 / 浮点 / 布尔参数解析失败一律抛 :class:`ValidationError` (HTTP 422),
  布尔真值集合为 ``1/true/yes/on``;
- 日期参数只接受 ``YYYY-MM-DD`` (同时容忍 ``YYYY/MM/DD``),
  ``date_from`` 落在当日 00:00:00, ``date_to`` 落在当日 23:59:59.999999 (闭区间);
- ``date_from > date_to``、``min > max`` 一律 422;
- 枚举型字段可在字段规格里声明 ``choices``, 出现未知取值时 422;
- 因子类字段可声明 ``upper``, 归一化时统一转大写。

归一化结果只包含可 JSON 序列化的基本类型, 日期为 ISO 字符串,
因此可以原样回传给前端 (``applied_filters``)。
"""
from datetime import datetime, time

from sqlalchemy import or_

from ..errors import ValidationError
from ..utils.validation import parse_date

# 统一的布尔真值集合; 其余取值视为非法参数 (而非 False)。
BOOL_TRUE = {"1", "true", "yes", "on"}
BOOL_FALSE = {"0", "false", "no", "off"}

# 归一化结果的日期序列化格式, 同时作为 applied_filters 的稳定输出格式。
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"


# ---------------------------------------------------------------------------
# 基础参数解析
# ---------------------------------------------------------------------------

def split_multi(value):
    """逗号分隔的多值参数 -> 去空白、去空段后的列表 (保留顺序, 不去重)。"""
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_multi(args, name):
    return split_multi(args.get(name))


def parse_int_list(args, name):
    """逗号分隔的整型列表; 任意一段不是整数都返回 422。"""
    values = []
    for item in split_multi(args.get(name)):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError(
                "%s 参数必须为整数" % name, fields={name: "invalid_integer"}
            )
    return values


def parse_float(args, name, required=False):
    raw = args.get(name)
    if raw in (None, ""):
        if required:
            raise ValidationError(
                "%s 参数不能为空" % name, fields={name: "required"}
            )
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "%s 参数必须为数字" % name, fields={name: "invalid_number"}
        )


def parse_bool(args, name):
    """三态布尔: 缺省 -> None; 非法取值 -> 422。"""
    raw = args.get(name)
    if raw in (None, ""):
        return None
    text = str(raw).strip().lower()
    if text in BOOL_TRUE:
        return True
    if text in BOOL_FALSE:
        return False
    raise ValidationError(
        "%s 参数必须为布尔值 (true/false)" % name, fields={name: "invalid_boolean"}
    )


def parse_date_bound(args, name, end_of_day=False):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, name)
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def parse_text(args, name):
    return (args.get(name) or "").strip()


def _serialize(value):
    if isinstance(value, datetime):
        return value.strftime(_DATE_FMT)
    return value


# ---------------------------------------------------------------------------
# 声明式字段规格
# ---------------------------------------------------------------------------

class FilterSpec:
    """单个筛选字段的解析规则。

    ``kind`` 取值:
      - ``multi``    逗号分隔字符串列表 (可带 choices / upper)
      - ``int_multi`` 逗号分隔整型列表
      - ``float``     单值浮点
      - ``bool``      三态布尔
      - ``date_from`` 起始日期 (当日零点)
      - ``date_to``   截止日期 (当日最后一刻)
      - ``text``      单值文本, strip 后保存
    """

    __slots__ = ("param", "key", "kind", "choices", "upper", "check_range")

    def __init__(self, key, kind, param=None, choices=None, upper=False, check_range=None):
        self.key = key
        self.param = param or key
        self.kind = kind
        self.choices = tuple(choices) if choices else None
        self.upper = upper
        self.check_range = check_range


def parse_filter_set(args, fields):
    """按字段规格把 request.args 解析成归一化字典, 并执行区间/枚举校验。"""
    result = {}
    for spec in fields:
        result[spec.key] = _parse_one(args, spec)

    for spec in fields:
        if spec.check_range:
            low_key, high_key, message = spec.check_range
            low = result.get(low_key)
            high = result.get(high_key)
            if low is not None and high is not None and low > high:
                raise ValidationError(message, fields={low_key: "range_invalid"})
    return result


def _parse_one(args, spec):
    kind = spec.kind
    if kind == "multi":
        values = split_multi(args.get(spec.param))
        if spec.upper:
            values = [item.upper() for item in values]
        if spec.choices:
            unknown = [item for item in values if item not in spec.choices]
            if unknown:
                raise ValidationError(
                    "%s 存在非法取值: %s" % (spec.param, ", ".join(sorted(set(unknown)))),
                    fields={spec.param: "unknown"},
                )
        return values
    if kind == "int_multi":
        return parse_int_list(args, spec.param)
    if kind == "float":
        return parse_float(args, spec.param)
    if kind == "bool":
        return parse_bool(args, spec.param)
    if kind == "date_from":
        return parse_date_bound(args, spec.param, end_of_day=False)
    if kind == "date_to":
        return parse_date_bound(args, spec.param, end_of_day=True)
    if kind == "text":
        return parse_text(args, spec.param)
    raise ValueError("未知筛选字段类型: %s" % kind)


def serialize_filters(filters):
    """归一化字典 -> 可 JSON 序列化版本 (datetime 转 ISO 字符串)。"""
    return {key: _serialize(value) for key, value in filters.items()}


# ---------------------------------------------------------------------------
# 声明式条件应用
# ---------------------------------------------------------------------------

def apply_conditions(query, filters, conditions):
    """按 ``conditions`` 列表把归一化筛选条件追加到 SQLAlchemy 查询上。

    每项为 ``(key, predicate)``: 当 ``filters[key]`` 为非空列表、True/False
    或非空字符串时才追加谓词; None / 空列表 / 空字符串一律跳过。
    """
    for key, predicate in conditions:
        value = filters.get(key)
        if value is None:
            continue
        if isinstance(value, (list, str)) and not value:
            continue
        query = predicate(query, value)
    return query


def in_(column):
    return lambda query, value: query.filter(column.in_(value))


def equal_(column):
    return lambda query, value: query.filter(column.is_(value))


def ge_(column):
    return lambda query, value: query.filter(column >= value)


def le_(column):
    return lambda query, value: query.filter(column <= value)


def like_(column):
    return lambda query, value: query.filter(column.like("%" + value + "%"))


def keyword_any_(*columns):
    """站点类关键字检索: 名称 / 编码 / 地址等任意一列模糊命中。"""
    def predicate(query, value):
        like = "%" + value + "%"
        return query.filter(or_(*[column.like(like) for column in columns]))

    return predicate
