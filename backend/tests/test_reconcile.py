"""存量数据口径核对/修复 (reconcile) 测试."""
from app.extensions import db
from app.models import Exceedance, Measurement
from app.services import reconcile_service


def _make_exceeded(client, station, entry_payload):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            entries=[{"pollutant": "SO2", "value": 900.0}, {"pollutant": "PM25", "value": 60.0}],
        ),
    )


def test_dry_run_reports_but_does_not_mutate(client, station, entry_payload):
    _make_exceeded(client, station, entry_payload)
    # 手工把一条超标记录的派生字段改坏, 模拟历史口径差异
    record = Measurement.query.filter_by(pollutant="SO2").one()
    record.is_exceeded = False
    record.exceed_ratio = 1.0

    report = reconcile_service.reconcile_measurements(apply=False)
    assert report["mode"] == "dry-run"
    assert report["measurements_checked"] == 2
    assert report["measurements_drifted"] == 1
    # dry-run 不落库
    assert Measurement.query.filter_by(pollutant="SO2").one().is_exceeded is False


def test_apply_repairs_pending_drift_and_creates_exceedance(client, station, entry_payload):
    _make_exceeded(client, station, entry_payload)
    record = Measurement.query.filter_by(pollutant="SO2").one()
    record.is_exceeded = False
    record.exceed_ratio = 1.0
    # 同步把超标记录摘掉, 模拟 "超标但没建单" 的历史差异
    Exceedance.query.delete()

    report = reconcile_service.reconcile_measurements(apply=True)
    assert report["exceedances_created"] == 1

    refreshed = Measurement.query.filter_by(pollutant="SO2").one()
    assert refreshed.is_exceeded is True
    assert round(refreshed.exceed_ratio, 3) == 1.8
    assert Exceedance.query.count() == 1
    assert Exceedance.query.one().status == "pending"


def test_apply_drops_exceedance_when_value_no_longer_exceeds(client, station, entry_payload):
    _make_exceeded(client, station, entry_payload)
    assert Exceedance.query.count() == 1
    record = Measurement.query.filter_by(pollutant="SO2").one()
    record.value = 100.0  # 低于 500 限值, 但派生字段仍是旧快照
    record.is_exceeded = True
    record.exceed_ratio = 1.8

    report = reconcile_service.reconcile_measurements(apply=True)
    assert report["exceedances_deleted"] == 1
    assert Measurement.query.filter_by(pollutant="SO2").one().is_exceeded is False
    assert Exceedance.query.count() == 0


def test_annotated_conflict_is_never_auto_modified(client, station, entry_payload):
    from app.services import exceedance_service

    _make_exceeded(client, station, entry_payload)
    exceedance = Exceedance.query.filter_by(pollutant="SO2").one()
    exceedance_service.annotate(
        exceedance, status="confirmed", note="人工复核确认", annotator="王敏"
    )
    # 改监测值使其不再超标, 制造与人工标注结论的冲突
    record = Measurement.query.filter_by(pollutant="SO2").one()
    record.value = 100.0
    record.is_exceeded = True

    report = reconcile_service.reconcile_measurements(apply=True)
    assert report["manual_conflicts"] == 1
    assert report["conflict_samples"][0]["exceedance_id"] == exceedance.id
    # 标注记录原样保留, 不删除不改状态
    refreshed = db.session.get(Exceedance, exceedance.id)
    assert refreshed.status == "confirmed"
    assert refreshed.note == "人工复核确认"
