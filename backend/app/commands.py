"""Flask CLI commands: flask init-db / seed / reset-db."""
import click

from .extensions import db
from .models import Exceedance, Measurement, Station


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        db.create_all()
        click.echo("数据库表已创建")

    @app.cli.command("seed")
    @click.option("--days", default=5, show_default=True, help="生成最近多少天的数据")
    @click.option("--force", is_flag=True, help="已有数据时仍然追加写入")
    def seed(days, force):
        """Load demo stations and monitoring records."""
        from .seed import seed_demo_data

        if Station.query.count() and not force:
            click.echo("已存在监测点数据, 如确需追加请使用 --force")
            return
        db.create_all()
        totals = seed_demo_data(days=days)
        click.echo(
            "演示数据写入完成: 监测点 %(stations)s 个, 监测数据 %(measurements)s 条, "
            "超标记录 %(exceedances)s 条" % totals
        )

    @app.cli.command("reset-db")
    @click.option("--with-demo/--empty", default=True, help="是否写入演示数据")
    def reset_db(with_demo):
        """Drop all tables, recreate them and optionally load demo data."""
        from .seed import reset_database, seed_demo_data

        reset_database()
        click.echo("数据库已重置")
        if with_demo:
            totals = seed_demo_data()
            click.echo("演示数据写入完成: %s" % totals)

    @app.cli.command("stats")
    def stats():
        """Print a short record summary."""
        click.echo(
            "监测点 %d 个 / 监测数据 %d 条 / 超标记录 %d 条"
            % (
                Station.query.count(),
                Measurement.query.count(),
                Exceedance.query.count(),
            )
        )

    @app.cli.command("reconcile")
    @click.option("--apply", "apply_changes", is_flag=True,
                  help="实际执行修复; 缺省为只读核对(dry-run), 仅打印差异")
    def reconcile(apply_changes):
        """按当前超标判定规则核对存量监测数据与超标记录的口径差异."""
        from .services.reconcile_service import reconcile_measurements

        report = reconcile_measurements(apply=apply_changes)
        click.echo("模式: %s" % ("实际修复" if apply_changes else "只读核对 (加 --apply 执行修复)"))
        click.echo(
            "监测数据核对 %(measurements_checked)d 条, 派生字段存在差异 %(measurements_drifted)d 条"
            % report
        )
        click.echo(
            "超标记录: 待新建 %(exceedances_created)d / 更新 %(exceedances_updated)d / "
            "撤销 %(exceedances_deleted)d; 已人工标注冲突 %(manual_conflicts)d 条(不自动处理)"
            % report
        )
        for sample in report["conflict_samples"]:
            click.echo(
                "  - 冲突: exceedance=%(exceedance_id)s measurement=%(measurement_id)s "
                "%(pollutant)s 状态=%(status)s" % sample
            )
