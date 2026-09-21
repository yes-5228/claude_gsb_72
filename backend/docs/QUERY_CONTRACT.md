# 统一查询与判定口径说明

本次改造把原先散落在「数据查询 / 监测数据录入 / 超标标注 / 台账 / 运行概览」
各页面、各统计入口里的筛选解析、列表状态、分页、导出、超标判定与达标率
计算收敛为一套实现。页面操作、字段含义、统计结果与导出内容均保持不变。

## 1. 收敛后的唯一真源

| 关注点 | 唯一实现 | 调用方（不允许再各写一份） |
| --- | --- | --- |
| 多值/日期/数值/布尔参数解析 | `app/services/filters.py`（`parse_filter_set` + 字段规格） | 三个列表服务 |
| 监测数据筛选谓词与排序 | `app/services/query_service.py`（`measurement_filter_set` / `apply_filters` / `measurement_query`） | `/measurements`、`/query/*`、`/meta/overview`、两处导出 |
| 超标记录筛选谓词与排序 | `app/services/exceedance_service.py`（`exceedance_filter_set` / `ordered_exceedance_query`） | 工作台、导出、首页待办 |
| 台账筛选谓词与排序 | `app/services/station_service.py`（`station_query`） | 台账列表 |
| 排序确定性兜底 | `app/services/list_query.py`（`apply_ordering`） | 所有列表 |
| 分页 | `app/utils/pagination.py`（未改语义） | 所有列表 |
| 超标判定与分级 | `app/domain/exceedance_rules.py`（GB 3095-2012 二级限值） | 录入、覆盖、预览、口径修复 |
| 超标率/达标率/精度 | `app/domain/metrics.py`（`ratio` / `rounded` / `ratio3`） | 查询汇总、分组聚合、超标统计 |
| CSV 列定义 | `app/utils/export_columns.py` | 三处导出 |
| 历史口径对齐 | `app/services/reconciliation.py` + `flask reconcile-exceedances` | 运维 |

前端对应收敛到 `src/constants/filters.js`（选项与初始筛选）、
`src/hooks/useFilterDraft.js`（筛选草稿状态）、`api/client.js` 的
`exportUrl`（导出地址拼装）。

## 2. 参数解析的统一约定

- **多值参数**：英文逗号分隔，去空白、去空段，保留顺序不去重；
  对应 SQL `IN (...)`。例：`pollutant=PM25,SO2`。
- **因子参数**：归一化统一转大写（`so2` 等价于 `SO2`），未知因子 422。
- **日期范围**：只接受 `YYYY-MM-DD`（容忍 `YYYY/MM/DD`）；
  `date_from` 取当日 `00:00:00`，`date_to` 取当日 `23:59:59.999999`，
  两端都闭，因此 `date_from=date_to` 表示"当天全天"。
  `date_from > date_to` 一律 422（此前超标记录入口缺少该校验）。
- **数值区间**：`min_value/max_value`、`min_ratio` 非数字一律 422；
  `min > max` 一律 422。
- **布尔**：真值 `1/true/yes/on`，假值 `0/false/no/off`，缺省为"不限"；
  其他取值（如 `is_exceeded=maybe`）一律 422（此前会被静默当成 false）。
- **枚举**：`period / data_source / exceedance_status / status / level /
  station_type / station status` 出现未知取值统一 422
  （此前仅 period/pollutant 等少数字段有校验）。
- **关键字**：仍是模糊匹配，但各实体语义保持历史定义——
  监测数据/台账匹配「站点名称/编码/地址」，超标工作台匹配「站点名称/编码/标注说明」。

归一化字段键沿用既有名称（`pollutants`、`station_ids`、`date_from` 等），
`/api/query/measurements` 的 `applied_filters` 结构保持不变。

## 3. 必须成立的不变量（已用测试锁定）

后端测试 `tests/test_query_consistency.py` 对以下契约做了断言，任何后续改动
都必须继续满足：

1. **同一条件、同一计数**：相同筛选参数下
   - `GET /measurements`、`GET /query/measurements` 的 `total` 与
     `GET /measurements/summary` 的 `total` 三者相等；
   - `/query/statistics` 各分组 `count` 之和（`totals.count`）等于列表 `total`；
   - 超标工作台 `summary.total` 等于列表 `total`（二者共用同一份已解析筛选，
     不再各解析一次）；
   - 概览页 `/meta/overview` 的监测数据总量、超标率与查询入口一致。
2. **同一条件、同一顺序**：所有列表排序统一为「主列 + 主键 id 兜底」
   （监测数据/超标记录 id 降序，台账 id 升序）。并列时顺序确定，
   翻页不会出现重复行或漏行；排序字段非法时回退默认值。
3. **同一条件、同一汇总**：超标率只有一个公式
   `超标条数 / 总条数，保留 4 位小数，分母为 0 时为 0.0`，
   查询汇总、分组统计、概览展示取值完全相同；浓度均值保留 2 位、
   超标倍数保留 3 位。
4. **列表与导出同源**：三处导出都走与列表相同的
   「解析 → 谓词 → 排序」管线，默认同为监测时间倒序；
   受 `MAX_EXPORT_ROWS=20000` 上限保护，未触顶时导出行数等于列表 `total`，
   列顺序/表头/单元格取值由 `export_columns.py` 单点定义。
5. **判定与记录一一对应**：一次写入中，`Measurement.is_exceeded=True`
   的条数等于生成的 `Exceedance` 条数；覆盖为达标值时超标记录撤销。
6. **JOIN 不放大行数**：标注状态过滤 JOIN `exceedances`，
   因 `measurement_id` 唯一，不会改变计数；站点信息 JOIN 同理。

## 4. 既有数据里已经存在的口径差异，以及处理方式

超标判定的真源是写入时执行的 `exceedance_rules`。存量库中可能因为**限值标准
调整、旧版本 bug、直接改库**等原因，出现与现行规则不一致的数据：

- `measurements.is_exceeded / limit_value / exceed_ratio` 与现行限值不符；
- 该超标却没有 `exceedances` 记录，或反之存在"孤儿"超标记录；
- 待标注记录的 `level` 与现行分级阈值不符；
- 也存在**合理的、必须保留的差异**：超标记录被人工确认/忽略后，
  即便底层数据被改回达标区间，也不能静默删除其标注痕迹；
  人工修正过的等级也不应被自动覆盖。

处理原则：**查询统计不做即时重算**（否则同一页面上列表与历史记录会"打架"），
而是提供独立的体检/修复命令，默认只读、修复保守：

```bash
flask --app wsgi reconcile-exceedances            # 只体检, 输出差异计数, 不写库
flask --app wsgi reconcile-exceedances --apply    # 按策略修复
```

修复策略（`services/reconciliation.py`）：

1. 所有监测数据按现行规则重算限值快照/倍数/超标标记并回写，统计口径随即统一；
2. 应超标却缺记录的，补建**待标注**记录，交人工复核；
3. 不该超标却有记录的：仍为待标注（无标注痕迹）才撤销；
   已确认/忽略的保留并计入 `kept_annotated`，绝不抹除人工标注；
4. 等级只刷新仍为待标注的记录，人工修正过的等级保持不变；
5. 命令幂等：在演示库上执行后再次体检差异为 0，监测点/数据/超标记录总数不变。

另外两类"看起来像差异、实际是定义如此"的情况，保持现状不改：

- **PM2.5/PM10 小时值**标准未设小时限值，只记录、永不判超标；
  因此这部分数据计入总条数但不产生超标，是现行口径的既定行为。
- 超标记录工作台的**等级是字符串码**（light/moderate/severe），
  排序沿用既有字符串序而非业务等级序，本次不改，避免改变既有顺序。

## 5. 行为兼容性小结

- 请求/响应字段、表头文案、列顺序、默认排序方向、分页默认值、
  导出文件名与 20000 行上限均未改变，前端四个页面的交互未改变。
- 仅有两处"非法输入"从"静默吞掉/返回空结果"收紧为 **422**：
  非法布尔值、各枚举字段的未知取值、超标入口的日期倒挂。
  页面下拉框与日期控件只会发出合法取值，因此不影响正常操作。
