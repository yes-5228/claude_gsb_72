"""存量监测数据与超标记录的口径核对 / 修复.

超标判定属于 "写入时快照": 限值、倍数、是否超标、等级在录入时由
``domain.exceedance_rules.evaluate`` 算出并落库 (见 README 设计说明,
限值调整不应反向改写历史)。因此历史数据可能与当前规则存在口径差异,
来源包括: 早期版本的规则缺陷、手工改库、写入中断等。

本模块提供单一的核对口径, 与录入路径完全一致 (都调用 evaluate),
默认只读 (dry-run) 只报差异; 显式 ``apply=True`` 时才修复, 且:

- 监测数据的派生字段 (limit_value / exceed_ratio / is_exceeded) 可直接刷新,
  监测值、限值快照以外的业务字段一律不动;
- 待标注(pending)超标记录可按当前口径 新建 / 更新 / 撤销;
- 已人工标注(confirmed/ignored)的记录绝不自动改写或删除,
  只列入 manual_conflicts 由业务复核, 避免抹掉标注留痕
  (判定未翻转、仅倍数/限值有精度差异时, 超标单作为标注证据整体冻结,
  只刷新监测数据侧派生字段)。
"""
from ..domain import exceedance_rules
from ..extensions import db
from ..models import Measurement
from .measurement_service import _sync_exceedance

_CONFLICT_SAMPLE_LIMIT = 50


def reconcile_measurements(apply=False):
    """全量核对监测数据与超标记录, 返回差异统计; apply=True 时执行修复."""
    report = {
        "mode": "apply" if apply else "dry-run",
        "measurements_checked": 0,
        "measurements_drifted": 0,
        "exceedances_created": 0,
        "exceedances_updated": 0,
        "exceedances_deleted": 0,
        "manual_conflicts": 0,
        "conflict_samples": [],
    }

    records = Measurement.query.order_by(Measurement.id.asc()).all()
    for record in records:
        report["measurements_checked"] += 1
        evaluation = exceedance_rules.evaluate(record.pollutant, record.period, record.value)
        exceedance = record.exceedance

        # 派生字段差异
        drift = (
            record.limit_value != evaluation["limit"]
            or record.exceed_ratio != evaluation["ratio"]
            or bool(record.is_exceeded) != bool(evaluation["exceeded"])
        )
        # 超标单层面差异 (待标注单才允许自动处理)
        needs_create = evaluation["exceeded"] and exceedance is None
        needs_delete = not evaluation["exceeded"] and exceedance is not None
        needs_level_update = (
            evaluation["exceeded"]
            and exceedance is not None
            and exceedance.status == "pending"
            and exceedance.level != evaluation["level"]
        )

        conflict = None
        if exceedance is not None and exceedance.status != "pending":
            # 人工标注过的记录: 仅当判定翻转或等级变化时阻止自动处理, 交人工复核;
            # 限值/倍数等快照精度差异不影响标注结论, 不视为冲突。
            level_changed = (
                evaluation["level"] is not None and exceedance.level != evaluation["level"]
            )
            if needs_delete or level_changed:
                conflict = {
                    "exceedance_id": exceedance.id,
                    "measurement_id": record.id,
                    "station_id": record.station_id,
                    "pollutant": record.pollutant,
                    "status": exceedance.status,
                    "reason": "已人工标注, 当前规则下判定结果不一致, 需人工复核",
                }

        if conflict is not None:
            report["manual_conflicts"] += 1
            if len(report["conflict_samples"]) < _CONFLICT_SAMPLE_LIMIT:
                report["conflict_samples"].append(conflict)
            continue

        if drift:
            report["measurements_drifted"] += 1
        if needs_create:
            report["exceedances_created"] += 1
        if needs_level_update:
            report["exceedances_updated"] += 1
        if needs_delete:
            report["exceedances_deleted"] += 1

        if not apply:
            continue

        # 刷新监测数据派生字段 (监测值本身不变)
        record.limit_value = evaluation["limit"]
        record.exceed_ratio = evaluation["ratio"]
        record.is_exceeded = evaluation["exceeded"]

        if needs_create or needs_level_update or needs_delete:
            _sync_exceedance(record, None, evaluation)
            db.session.flush()

    if apply:
        db.session.commit()
    return report
