"""跨入口口径一致性不变量测试。

覆盖改造后必须长期成立的契约:

1. 同一筛选条件下, 列表 total / 汇总 total / 聚合 totals / 导出行数一致;
2. 各列表入口默认顺序稳定 (并列时 id 兜底), 翻页不重不漏;
3. 超标率在"查询汇总 / 分组统计 / 概览"任意入口取值相同;
4. 多值条件 (逗号分隔)、日期范围在 measurements 与 query 两个入口结果一致;
5. 超标工作台 summary.total 与列表 total 恒等;
6. 既有脏数据可被体检发现并按保守策略修复, 人工标注不丢失。
"""
from app.domain import exceedance_rules
from app.extensions import db
from app.models import Exceedance, Measurement
from app.services import exceedance_service, reconciliation


def _entry(station_id, day, pollutant, value, period="daily"):
    return {
        "station_id": station_id,
        "measured_at": "2026-09-%02d 10:00" % day,
        "period": period,
        "entries": [{"pollutant": pollutant, "value": value}],
    }


def _seed(client, station):
    # 两条超标 (SO2 600/900), 两条达标
    for day, value in ((1, 600.0), (2, 900.0), (3, 100.0), (4, 100.0)):
        client.post("/api/measurements/entries", json=_entry(station.id, day, "SO2", value))


# ---------------------------------------------------------------------------
# 1. 列表 / 汇总 / 聚合 / 导出口径一致
# ---------------------------------------------------------------------------

def test_list_summary_statistics_totals_agree(client, station):
    _seed(client, station)

    listed = client.get("/api/query/measurements").get_json()
    assert listed["total"] == 4
    assert listed["summary"]["total"] == 4

    stats = client.get("/api/query/statistics?group_by=pollutant&metric=count").get_json()
    assert stats["totals"]["count"] == 4
    so2 = next(item for item in stats["items"] if item["key"] == "SO2")
    assert so2["exceeded_count"] == 2
    assert so2["exceed_rate"] == 0.5

    # measurements 入口与 query 入口对同一参数返回同一 total
    other = client.get("/api/measurements?pollutant=SO2").get_json()
    direct = client.get("/api/query/measurements?pollutant=SO2").get_json()
    assert other["total"] == direct["total"] == 4
    assert other["summary"]["exceed_rate"] == direct["summary"]["exceed_rate"] == 0.5


def test_export_rows_match_filtered_list(client, station):
    _seed(client, station)
    for pollutant in ("SO2",):
        listed = client.get("/api/query/measurements?pollutant=%s" % pollutant).get_json()
        export = client.get("/api/query/export?pollutant=%s" % pollutant)
        lines = export.get_data(as_text=True).strip().splitlines()
        # 表头 + 数据行; 数据受 MAX_EXPORT_ROWS 保护, 小数据集下应与 total 相等
        assert len(lines) - 1 == listed["total"]


def test_multi_value_and_date_range_agree_across_entries(client, station):
    _seed(client, station)
    client.post("/api/measurements/entries", json=_entry(station.id, 1, "NO2", 300.0))

    # 多值因子
    multi = client.get("/api/query/measurements?pollutant=SO2,NO2").get_json()
    assert multi["total"] == 5

    # 日期范围: 闭区间, 9 月 2 日当天包含在内
    ranged = client.get("/api/query/measurements?date_from=2026-09-02&date_to=2026-09-03").get_json()
    assert ranged["total"] == 2
    assert ranged["summary"]["total"] == 2


def test_pagination_uses_deterministic_ordering(client, station):
    _seed(client, station)
    page1 = client.get("/api/query/measurements?page=1&page_size=2").get_json()["items"]
    page2 = client.get("/api/query/measurements?page=2&page_size=2").get_json()["items"]
    ids = [item["id"] for item in page1 + page2]
    assert len(ids) == len(set(ids)) == 4
    # 默认 measured_at 倒序
    times = [item["measured_at"] for item in page1] + [item["measured_at"] for item in page2]
    assert times == sorted(times, reverse=True)


def test_exceedance_list_and_summary_share_filters(client, station):
    _seed(client, station)
    body = client.get("/api/exceedances?status=pending").get_json()
    assert body["total"] == body["summary"]["total"] == 2

    only_severe = client.get("/api/exceedances?level=severe").get_json()
    assert only_severe["total"] == only_severe["summary"]["total"]
    assert only_severe["total"] == 2
    assert {item["level"] for item in only_severe["items"]} == {"severe"}


def test_overview_uses_same_rate(client, station):
    _seed(client, station)
    overview = client.get("/api/meta/overview").get_json()
    direct = client.get("/api/query/measurements").get_json()["summary"]
    assert overview["measurements"]["total"] == direct["total"]
    assert overview["measurements"]["exceed_rate"] == direct["exceed_rate"]


# ---------------------------------------------------------------------------
# 2. 参数校验在所有入口统一
# ---------------------------------------------------------------------------

def test_invalid_bool_and_choice_rejected_everywhere(client, station):
    assert client.get("/api/query/measurements?is_exceeded=maybe").status_code == 422
    assert client.get("/api/measurements?is_exceeded=maybe").status_code == 422
    assert client.get("/api/query/measurements?data_source=bogus").status_code == 422
    assert client.get("/api/exceedances?status=bogus").status_code == 422
    assert client.get("/api/exceedances?level=bogus").status_code == 422
    assert client.get("/api/stations?status=bogus").status_code == 422
    assert client.get("/api/exceedances?date_from=2026-09-05&date_to=2026-09-01").status_code == 422


# ---------------------------------------------------------------------------
# 3. 存量口径差异: 体检 + 保守修复
# ---------------------------------------------------------------------------

def test_reconcile_detects_and_fixes_drift(app, client, station):
    _seed(client, station)

    # 人为制造口径漂移: 把一条超标的 SO2 标记洗成"达标"并删掉超标记录,
    # 另保留一条带人工标注的超标记录。
    drifted = Measurement.query.filter(
        Measurement.pollutant == "SO2", Measurement.is_exceeded.is_(True)
    ).order_by(Measurement.id.asc()).first()
    db.session.delete(drifted.exceedance)
    drifted.is_exceeded = False
    drifted.limit_value = 999.0
    drifted.exceed_ratio = 0.1

    annotated = Exceedance.query.join(Measurement).filter(
        Measurement.pollutant == "SO2"
    ).order_by(Exceedance.id.asc()).first()
    exceedance_service.annotate(
        annotated, status="confirmed", note="人工已确认, 修复时必须保留", annotator="测试员"
    )
    # 让该记录在现行规则下"不该超标", 但因已标注应被保留
    annotated.measurement.value = 10.0
    annotated.measurement.is_exceeded = False
    db.session.commit()

    with app.app_context():
        report = reconciliation.scan_reconciliation()
        assert report["counts"]["stale_measurements"] >= 2
        assert drifted.id in report["missing_exceedances"]
        assert report["counts"]["kept_annotated"] == 1

        fixed = reconciliation.apply_reconciliation()
        assert fixed["fixed"]["created_exceedances"] == 1
        assert fixed["fixed"]["kept_annotated"] == 1

        db.session.expire_all()
        refreshed = db.session.get(Measurement, drifted.id)
        assert refreshed.is_exceeded is True
        assert refreshed.exceedance is not None
        assert refreshed.exceedance.status == "pending"

        kept = db.session.get(Exceedance, annotated.id)
        assert kept.status == "confirmed"
        assert kept.note == "人工已确认, 修复时必须保留"


def test_evaluate_is_single_source_of_truth():
    """写入路径与修复路径必须调用同一个判定函数 (同一限值与分级口径)。"""
    result = exceedance_rules.evaluate("SO2", "daily", 300.0)
    assert result["exceeded"] is True
    assert result["limit"] == 150.0
    assert result["ratio"] == 2.0
    assert result["level"] == "severe"
