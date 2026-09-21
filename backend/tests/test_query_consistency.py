"""统一查询口径的跨入口不变量测试.

同一组筛选参数在 监测数据列表 / 录入页列表 / 两个导出 / 聚合统计 / 概览
之间必须得到相同的命中条数、行集合与汇总; 超标工作台的列表/统计/导出同理。
"""
from app.services import exceedance_service, query_service


def _seed_two_days(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            period="daily",
            entries=[{"pollutant": "PM25", "value": 60.0}, {"pollutant": "SO2", "value": 900.0}],
        ),
    )
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-02 10:00",
            period="daily",
            entries=[{"pollutant": "PM25", "value": 100.0}, {"pollutant": "SO2", "value": 100.0}],
        ),
    )


def test_measurement_entrypoints_share_rows_and_order(client, station, entry_payload):
    _seed_two_days(client, station, entry_payload)
    params = {"pollutant": "PM25", "sort": "measured_at", "order": "desc"}

    from app.services.measurement_filters import build_measurement_query

    query_query, _ = build_measurement_query(params)
    measurements_query, _ = query_service.measurement_query(dict(params))
    assert [row.id for row in query_query.all()] == [row.id for row in measurements_query.all()]

    # /query 与 /measurements 两个 HTTP 入口的 total 与 items 顺序一致
    via_query = client.get("/api/query/measurements?pollutant=PM25&sort=measured_at&order=desc").get_json()
    via_measurements = client.get("/api/measurements?pollutant=PM25&sort=measured_at&order=desc").get_json()
    assert via_query["total"] == via_measurements["total"] == 2
    assert [item["id"] for item in via_query["items"]] == [
        item["id"] for item in via_measurements["items"]
    ]

    # 导出命中同一批行 (查询导出 13 列, 录入导出 14 列, 行数一致)
    query_csv = client.get("/api/query/export?pollutant=PM25").get_data(as_text=True).strip().splitlines()
    measurements_csv = client.get("/api/measurements/export?pollutant=PM25").get_data(as_text=True).strip().splitlines()
    assert len(query_csv) == 3
    assert len(measurements_csv) == 3
    # 前 13 列取值必须逐行相同 (录入导出仅多最后的备注列)
    for left, right in zip(query_csv[1:], measurements_csv[1:]):
        assert left == right.rsplit(",", 1)[0]


def test_statistics_totals_match_list_summary(client, station, entry_payload):
    _seed_two_days(client, station, entry_payload)
    params = "?period=daily&date_from=2026-09-01&date_to=2026-09-02"

    listing = client.get("/api/query/measurements" + params).get_json()
    stats = client.get("/api/query/statistics" + params + "&group_by=pollutant&metric=count").get_json()

    assert stats["totals"]["count"] == listing["total"]
    assert stats["totals"]["exceeded_count"] == listing["summary"]["exceeded_count"]
    # 每个因子都是一超一不超, 组内超标率 0.5; 汇总口径同为 超标2/总数4 = 0.5
    assert listing["summary"]["exceed_rate"] == 0.5
    for item in stats["items"]:
        assert item["count"] == 2
        assert item["exceeded_count"] == 1
        assert item["exceed_rate"] == 0.5


def test_overview_reuses_same_summary(client, station, entry_payload):
    _seed_two_days(client, station, entry_payload)
    overview = client.get("/api/meta/overview").get_json()
    full_list = client.get("/api/query/measurements").get_json()
    assert overview["measurements"]["total"] == full_list["summary"]["total"]
    assert overview["measurements"]["exceed_rate"] == full_list["summary"]["exceed_rate"]


def test_enum_typos_are_rejected_everywhere(client, station, entry_payload):
    _seed_two_days(client, station, entry_payload)
    assert client.get("/api/query/measurements?data_source=bogus").status_code == 422
    assert client.get("/api/query/measurements?station_type=bogus").status_code == 422
    assert client.get("/api/query/measurements?exceedance_status=bogus").status_code == 422
    assert client.get("/api/exceedances?status=bogus").status_code == 422
    assert client.get("/api/exceedances?level=bogus").status_code == 422
    assert client.get("/api/exceedances?pollutant=xx").status_code == 422


def test_date_range_order_validated_in_both_domains(client):
    bad = "?date_from=2026-09-10&date_to=2026-09-01"
    assert client.get("/api/query/measurements" + bad).status_code == 422
    assert client.get("/api/exceedances" + bad).status_code == 422


def test_exceedance_entrypoints_share_rows_and_summary(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            entries=[
                {"pollutant": "SO2", "value": 600.0},
                {"pollutant": "NO2", "value": 300.0},
                {"pollutant": "PM25", "value": 40.0},
            ],
        ),
    )
    params = "?pollutant=SO2&level=light"
    listing = client.get("/api/exceedances" + params).get_json()
    assert listing["total"] == listing["summary"]["total"] == 1

    csv_lines = client.get("/api/exceedances/export" + params).get_data(as_text=True).strip().splitlines()
    assert len(csv_lines) == 2

    # 服务层同参数: 列表与统计基于同一筛选构造
    service_rows = exceedance_service.exceedance_query({"pollutant": "SO2", "level": "light"}).all()
    assert len(service_rows) == 1
    # 仅因子过滤时同时命中轻度的 SO2 与中度的 NO2, 与超标工作台无等级筛选口径一致
    assert exceedance_service.summary({"pollutant": "SO2"})["total"] == 1
    assert exceedance_service.summary({})["total"] == 2
