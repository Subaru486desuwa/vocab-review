import os

import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext

from app import clock
from app.repositories import db, migrations, users
from app.services import accounts, content_import, learning_state

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


@click.command("import-content")
@click.argument("directory", type=click.Path(file_okay=False))
@click.option("--dry-run", is_flag=True, help="只预检并报告变化，不写入。")
@with_appcontext
def import_content_command(directory, dry_run):
    """导入内容包目录（wordbooks.csv、words.csv 等，见 docs/content-format.md）。"""
    config = current_app.config
    click.echo(f"目标库：{config.get('DB_NAME')}@{config.get('DB_HOST')}:{config.get('DB_PORT')}")
    try:
        texts = content_import.read_directory(directory)
        summary = content_import.import_content(db.get_db(), texts, clock.now(), dry_run=dry_run)
    except content_import.ImportFailed as exc:
        for error in exc.errors[:200]:
            click.echo(f"{error.file}:{error.line} {error.message}")
        click.echo(f"预检未通过：{len(exc.errors)} 处错误，未写入任何数据。")
        raise click.exceptions.Exit(1) from exc
    for name, counts in summary.items():
        line = f"{name}：新增 {counts['inserted']}，更新 {counts['updated']}，未变 {counts['unchanged']}"
        if "retired" in counts:
            line += f"，停用旧版本 {counts['retired']}"
        click.echo(line)
    click.echo("预检通过，未写入。" if dry_run else "已提交。")


@click.command("seed-demo-user")
@click.option(
    "--username", default=lambda: os.environ.get("DEMO_USERNAME", "demo"), show_default="DEMO_USERNAME 或 demo"
)
@with_appcontext
def seed_demo_user_command(username):
    """创建演示学习者；密码取自环境变量 DEMO_USER_PASSWORD，已存在时不修改。"""
    password = os.environ.get("DEMO_USER_PASSWORD")
    if not password:
        raise click.ClickException("未设置 DEMO_USER_PASSWORD")
    try:
        with db.transaction() as conn:
            user = accounts.register(conn, username, password, clock.now())
    except accounts.UsernameTaken:
        click.echo(f"演示账户已存在：{username}（未修改密码）")
        return
    except accounts.ValidationFailed as exc:
        raise click.ClickException("；".join(exc.fields.values())) from exc
    click.echo(f"已创建演示账户：{user['username']}")


@click.command("rebuild-learning-state")
@click.option("--username", help="只核对该用户。")
@click.option("--apply", "apply_changes", is_flag=True, help="把不一致的学习状态改写为重放结果。")
@with_appcontext
def rebuild_learning_state_command(username, apply_changes):
    """按作答事实重放 review_rules，与 learning_state 比对；有差异且未加 --apply 时退出码为 1。"""
    conn = db.get_db()
    user_id = None
    if username:
        with db.transaction(conn):
            user = users.find_by_username_norm(conn, accounts.normalize_username(username))
        if user is None:
            raise click.ClickException(f"用户不存在：{username}")
        user_id = user["id"]
    try:
        diffs, checked = learning_state.compare(conn, user_id)
        if diffs and apply_changes:
            diffs = learning_state.rebuild(conn, user_id)
    except learning_state.UnknownRuleVersion as exc:
        raise click.ClickException(f"未知复习规则版本：{exc.args[0]}") from exc
    if not diffs:
        click.echo(f"学习状态与作答记录一致：核对 {checked} 组（用户, 词义, 题型）。")
        return
    click.echo(f"发现 {len(diffs)} 条不一致：")
    for diff in diffs:
        user, sense, skill = diff["key"]
        detail = "；".join(f"{field} 存储 {old} / 重建 {new}" for field, (old, new) in diff["changed"].items())
        click.echo(f"  user={user} sense={sense} skill={skill}：{detail}")
    if apply_changes:
        click.echo(f"已按作答记录重建 {len(diffs)} 条学习状态。")
        return
    raise click.exceptions.Exit(1)


def init_app(app):
    app.cli.add_command(db_cli)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(import_content_command)
    app.cli.add_command(seed_demo_user_command)
    app.cli.add_command(rebuild_learning_state_command)
