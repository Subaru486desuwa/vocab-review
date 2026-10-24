import json
import os
from pathlib import Path

import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext

from app import clock
from app.repositories import db, migrations, users
from app.repositories import examples as examples_repo
from app.repositories import models as model_repo
from app.services import accounts, content_import, example_search, learning_state, recall_model

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


@click.command("register-model")
@click.argument("directory", type=click.Path(file_okay=False))
@with_appcontext
def register_model_command(directory):
    """校验模型目录的清单与制品哈希，并登记到 model_versions；Web 只加载已登记的制品。"""
    try:
        manifest = recall_model.read_manifest(directory)
        recall_model.verify_artifact(directory, manifest)
    except recall_model.ModelUnavailable as exc:
        raise click.ClickException(str(exc)) from exc
    sha = manifest["artifact"]["sha256"]
    with db.transaction() as conn:
        row = model_repo.find_model_version(conn, manifest["model_code"], manifest["version"])
        if row is not None:
            if row["artifact_sha256"] != sha:
                raise click.ClickException(
                    f"{manifest['model_code']} {manifest['version']} 已登记为其他制品；新制品须使用新版本号"
                )
            click.echo(f"已登记：{manifest['model_code']} {manifest['version']}（id={row['id']}），未修改。")
            return
        model_id = model_repo.insert_model_version(
            conn,
            kind=manifest["kind"],
            model_code=manifest["model_code"],
            version=manifest["version"],
            artifact_sha256=sha,
            feature_schema_version=manifest["feature_schema_version"],
            metadata_json=json.dumps(manifest, ensure_ascii=False),
        )
    click.echo(
        f"已登记 {manifest['model_code']} {manifest['version']}（id={model_id}），"
        f"制品 {Path(directory) / manifest['artifact']['file']}"
    )


def _dl_dir():
    path = Path(current_app.config["DL_MODEL_DIR"])
    return path if path.is_absolute() else Path(current_app.root_path).parent / path


@click.command("build-example-index")
@with_appcontext
def build_example_index_command():
    """按当前启用例句离线构建向量索引，并登记编码器；例句变化后需重新执行。"""
    from ml import example_index

    with db.transaction() as conn:
        rows = examples_repo.active_examples(conn)
    try:
        manifest = example_index.build(_dl_dir(), rows)
        encoder = json.loads((_dl_dir() / "encoder" / example_index.ENCODER_MANIFEST).read_text(encoding="utf-8"))
        with db.transaction() as conn:
            model_id, created = example_search.register_encoder(conn, encoder, manifest, example_index.WEIGHTS)
    except (example_index.IndexUnavailable, example_index.TextTooLong, example_search.SearchUnavailable) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(
        f"已构建索引：{manifest['count']} 条例句，{manifest['dimensions']} 维 {manifest['dtype']}，"
        f"语料指纹 {manifest['corpus_fingerprint'][:16]}"
    )
    click.echo(
        f"编码器 {example_search.MODEL_CODE} @ {encoder['revision']}："
        f"{'已登记' if created else '沿用已登记'}（id={model_id}）"
    )


# 查询文件中 annotation 字段到报告用语的映射；混合或未知状态按最弱的说法报告。
ANNOTATION_STATUS = {
    "human_reviewed": "人工确认",
    "ai_reviewed": "AI 起草并经 AI 复核，不是独立人工标注",
    "unknown": "AI 草拟、待确认，不是独立人工标注",
}


@click.command("evaluate-example-search")
@click.option("--queries", default="data/demo/eval/example_queries.jsonl", show_default=True)
@click.option("--out", default=None, help="输出目录，默认 DL_MODEL_DIR/eval。")
@with_appcontext
def evaluate_example_search_command(queries, out):
    """用当前索引在 dev/test 查询上评价句向量检索与 TF-IDF，写出 metrics.json 与 evaluation.md。"""
    from ml import evaluate_examples, example_index

    try:
        model, encoder = example_index.load_encoder(_dl_dir())
        vectors, ids, index_manifest = example_index.load_index(_dl_dir(), encoder)
    except example_index.IndexUnavailable as exc:
        raise click.ClickException(str(exc)) from exc
    with db.transaction() as conn:
        rows = examples_repo.active_examples(conn)
    if example_index.corpus_fingerprint(rows) != index_manifest["corpus_fingerprint"]:
        raise click.ClickException("启用例句已变化，索引已过期；请先执行 flask build-example-index")
    loaded = evaluate_examples.load_queries(queries, {item["example_key"] for item in ids})
    statuses = sorted({q.get("annotation", "unknown") for q in loaded})
    status = ANNOTATION_STATUS.get(statuses[0] if len(statuses) == 1 else "unknown", ANNOTATION_STATUS["unknown"])
    result = evaluate_examples.run(model, vectors, ids, rows, loaded, example_index.encode)
    out_dir = Path(out) if out else _dl_dir() / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"annotation_status": status, "queries_file": queries, "index": index_manifest, "result": result}
    (out_dir / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "evaluation.md").write_text(
        evaluate_examples.render_report(result, index_manifest, status), encoding="utf-8"
    )
    for split, methods in result.items():
        for method, m in methods.items():
            click.echo(
                f"{split} {method}: Recall@3 {m['recall_at_3']} MRR@3 {m['mrr_at_3']}"
                f"（{m['with_relevant']} 条有相关项）"
            )
    click.echo(f"标注状态：{status}；结果写入 {out_dir}")


def init_app(app):
    app.cli.add_command(db_cli)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(import_content_command)
    app.cli.add_command(seed_demo_user_command)
    app.cli.add_command(rebuild_learning_state_command)
    app.cli.add_command(register_model_command)
    app.cli.add_command(build_example_index_command)
    app.cli.add_command(evaluate_example_search_command)
