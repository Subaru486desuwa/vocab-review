import click
from flask import current_app
from flask.cli import AppGroup

from app import clock
from app.repositories import db, migrations

db_cli = AppGroup("db", help="数据库迁移。")


@db_cli.command("upgrade")
def upgrade_command():
    """对 DB_NAME 指定的库执行未应用的迁移。"""
    config = current_app.config
    click.echo(f"目标库：{config.get('DB_NAME')}@{config.get('DB_HOST')}:{config.get('DB_PORT')}")
    try:
        conn = db.connect(config)
    except db.DatabaseNotConfigured as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        done = migrations.upgrade(conn, clock.now())
    finally:
        conn.close()
    click.echo("已执行：" + ", ".join(done) if done else "没有待执行的迁移。")


def init_app(app):
    app.cli.add_command(db_cli)
