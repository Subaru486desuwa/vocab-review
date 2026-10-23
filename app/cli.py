import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext

from app import clock
from app.repositories import db, migrations
from app.services import accounts

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


@click.command("create-admin")
@click.option("--username", prompt="用户名", help="3—32 位字母、数字或下划线。")
@with_appcontext
def create_admin_command(username):
    """创建管理员账户；密码在终端隐藏输入，不经命令行参数传递。"""
    password = click.prompt("密码", hide_input=True, confirmation_prompt="再次输入密码")
    try:
        with db.transaction() as conn:
            user = accounts.register(conn, username, password, clock.now(), role="admin")
    except accounts.ValidationFailed as exc:
        raise click.ClickException("；".join(exc.fields.values())) from exc
    except accounts.UsernameTaken as exc:
        raise click.ClickException("用户名已被使用") from exc
    click.echo(f"已创建管理员：{user['username']}（id={user['id']}）")


def init_app(app):
    app.cli.add_command(db_cli)
    app.cli.add_command(create_admin_command)
