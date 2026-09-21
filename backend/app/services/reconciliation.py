"""历史数据口径对齐: 用当前限值规则重算存量监测数据的判定结果。

超标判定只有一个真源 (:mod:`app.domain.exceedance_rules`), 写入路径
(录入 / 覆盖 / 种子) 都经过它。但既有数据库里可能存在口径漂移:

- 限值标准调整前写入的旧数据, ``is_exceeded`` / ``limit_value`` /
  ``exceed_ratio`` 与现行规则不一致;
- 历史脏数据出现 Measurement 判定标记与 Exceedance 记录不一一对应
  (有标记无记录, 或有记录但已不超标);
- 等级阈值调整后, 旧记录的 ``level`` 与新阈值不一致。

本模块提供**只读体检 (dry-run)** 与**按策略修复**两个动作, 修复策略刻意保守:

1. 监测数据的限值快照 / 倍数 / 超标标记按当前规则重算并回写;
2. "本不超标却存在超标记录"的记录: 若仍为待标注 (无人工标注痕迹) 则撤销,
   已被人工确认/忽略的保留, 仅计入 ``kept_annotated``, 不抹除标注痕迹;
3. "应超标却没有超标记录"的记录: 新建**待标注**记录, 等待人工复核;
4. 等级仅在超标记录仍为待标注时按新阈值刷新, 人工修正过的等级保持不变。

这样统计口径 (Measurement.is_exceeded) 与唯一真源一致, 而人工标注结果永不丢失。
"""
from ..domain import exceedance_rules
from ..extensions import db
from ..models import Exceedance, Measurement


def _recompute(measurement):
    """按当前规则重算一条监测数据, 返回 (evaluation, snapshot)。"""
    evaluation = exceedance_rules.evaluate(
        measurement.pollutant, measurement.period, measurement.value
    )
    snapshot = {
        "limit_value": evaluation["limit"],
        "exceed_ratio": evaluation["ratio"],
        "is_exceeded": evaluation["exceeded"],
        "level": evaluation["level"],
    }
    return evaluation, snapshot


def _is_annotation_clean(exceedance):
    return (
        exceedance is not None
        and exceedance.status == "pending"
        and not exceedance.annotated_at
    )


def scan_reconciliation():
    """只读体检: 返回各口径差异的明细与计数, 不写库。"""
    report = {
        "checked": 0,
        "stale_measurements": [],
        "missing_exceedances": [],
        "stale_pending_levels": [],
        "kept_annotated": [],
    }
    measurements = Measurement.query.order_by(Measurement.id.asc()).all()
    for measurement in measurements:
        report["checked"] += 1
        evaluation, snapshot = _recompute(measurement)
        exceedance = measurement.exceedance

        flag_drift = (
            bool(measurement.is_exceeded) != snapshot["is_exceeded"]
            or measurement.limit_value != snapshot["limit_value"]
            or measurement.exceed_ratio != snapshot["exceed_ratio"]
        )
        if flag_drift:
            report["stale_measurements"].append(measurement.id)

        if snapshot["is_exceeded"] and exceedance is None:
            report["missing_exceedances"].append(measurement.id)

        if not snapshot["is_exceeded"] and exceedance is not None:
            if _is_annotation_clean(exceedance):
                report["stale_pending_levels"].append(
                    {"measurement_id": measurement.id, "exceedance_id": exceedance.id,
                     "action": "remove_orphan"}
                )
            else:
                report["kept_annotated"].append(
                    {"measurement_id": measurement.id, "exceedance_id": exceedance.id,
                     "status": exceedance.status}
                )

        if snapshot["is_exceeded"] and exceedance is not None and exceedance.status == "pending":
            if exceedance.level != snapshot["level"]:
                report["stale_pending_levels"].append(
                    {"measurement_id": measurement.id, "exceedance_id": exceedance.id,
                     "action": "refresh_level", "level": snapshot["level"]}
                )

    report["counts"] = {
        "stale_measurements": len(report["stale_measurements"]),
        "missing_exceedances": len(report["missing_exceedances"]),
        "stale_pending_levels": len(report["stale_pending_levels"]),
        "kept_annotated": len(report["kept_annotated"]),
    }
    return report


def apply_reconciliation():
    """按保守策略修复口径差异, 返回与体检结构一致的修复报告。"""
    report = scan_reconciliation()
    fixed = {"refreshed_measurements": 0, "created_exceedances": 0,
             "removed_orphans": 0, "refreshed_levels": 0, "kept_annotated": 0}

    for measurement in Measurement.query.order_by(Measurement.id.asc()).all():
        evaluation, snapshot = _recompute(measurement)
        exceedance = measurement.exceedance

        measurement.limit_value = snapshot["limit_value"]
        measurement.exceed_ratio = snapshot["exceed_ratio"]
        measurement.is_exceeded = snapshot["is_exceeded"]
        if measurement.unit is None:
            measurement.unit = evaluation.get("unit")
        fixed["refreshed_measurements"] += 1

        if snapshot["is_exceeded"] and exceedance is None:
            measurement.exceedance = Exceedance(
                station_id=measurement.station_id,
                pollutant=measurement.pollutant,
                period=measurement.period,
                measured_at=measurement.measured_at,
                value=measurement.value,
                limit_value=snapshot["limit_value"],
                exceed_ratio=snapshot["exceed_ratio"],
                level=snapshot["level"],
                status="pending",
            )
            fixed["created_exceedances"] += 1
        elif not snapshot["is_exceeded"] and exceedance is not None:
            if _is_annotation_clean(exceedance):
                db.session.delete(exceedance)
                fixed["removed_orphans"] += 1
            else:
                fixed["kept_annotated"] += 1
        elif snapshot["is_exceeded"] and exceedance is not None and exceedance.status == "pending":
            if exceedance.level != snapshot["level"]:
                exceedance.level = snapshot["level"]
                fixed["refreshed_levels"] += 1
            exceedance.limit_value = snapshot["limit_value"]
            exceedance.exceed_ratio = snapshot["exceed_ratio"]
            exceedance.value = measurement.value
            exceedance.measured_at = measurement.measured_at

    db.session.commit()
    report["fixed"] = fixed
    return report
