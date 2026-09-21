"""统一列表查询管线: 排序 (含确定性次序) 与分页。

不变量:

- 同一筛选条件下, 任何入口拿到的行顺序都由同一份排序规则决定;
- 排序主列出现并列时, 一律以主键 ``id`` 降序兜底, 保证翻页/导出/统计
  不会因数据库行序不确定而出现重复或遗漏;
- 分页参数 (page/page_size) 与行数据序列化在所有列表入口表现一致。
"""
from ..utils.pagination import paginate_query


def apply_ordering(query, args, columns, default_sort, default_order="desc",
                   tie_breaker=None):
    """按请求参数排序, 非法字段回退默认值, 并追加确定性的主键兜底列。

    :param columns: ``{sort_key: 模型列}`` 映射。
    :param default_sort: 默认排序键, 必须存在于 columns。
    :param default_order: 默认方向。
    :param tie_breaker: 并列时的兜底列 (一般是 ``Model.id.desc()``)。
    """
    sort_key = args.get("sort") or default_sort
    column = columns.get(sort_key, columns[default_sort])
    direction = (args.get("order") or default_order).lower()
    primary = column.desc() if direction == "desc" else column.asc()
    if tie_breaker is not None:
        return query.order_by(primary, tie_breaker)
    return query.order_by(primary)


def run_paginated(query, serializer, page=None, page_size=None):
    """分页序列化, 默认走全局 page_params (从 request.args 取分页参数)。"""
    return paginate_query(query, serializer, page=page, page_size=page_size)
