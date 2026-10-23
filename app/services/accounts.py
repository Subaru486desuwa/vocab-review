import re
from functools import cache

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories import users

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,32}")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
_DUPLICATE_KEY = 1062


class ValidationFailed(Exception):
    def __init__(self, fields):
        super().__init__("字段校验失败")
        self.fields = fields


class UsernameTaken(Exception):
    pass


def normalize_username(username):
    return username.strip().lower()


def validate(username, password):
    """返回字段到错误说明的映射；为空表示通过。"""
    fields = {}
    if not USERNAME_PATTERN.fullmatch(username.strip()):
        fields["username"] = "用户名为 3—32 位字母、数字或下划线"
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        fields["password"] = f"密码长度为 {PASSWORD_MIN_LENGTH}—{PASSWORD_MAX_LENGTH} 位"
    return fields


def public_user(row):
    return {key: row[key] for key in ("id", "username", "role", "display_timezone")}


def register(conn, username, password, now, role="learner"):
    """创建账户；注册入口只创建 learner，管理员由命令行传入 role。"""
    fields = validate(username, password)
    if fields:
        raise ValidationFailed(fields)
    username_norm = normalize_username(username)
    if users.find_by_username_norm(conn, username_norm) is not None:
        raise UsernameTaken
    try:
        user_id = users.insert(
            conn,
            username=username.strip(),
            username_norm=username_norm,
            password_hash=generate_password_hash(password),
            role=role,
            created_at=now,
        )
    except pymysql.err.IntegrityError as exc:
        # 并发注册同名时由唯一约束兜底。
        if exc.args[0] == _DUPLICATE_KEY:
            raise UsernameTaken from exc
        raise
    return users.find_by_id(conn, user_id)


def authenticate(conn, username, password):
    """用户名与密码均正确且账户启用时返回用户行，否则返回 None。"""
    row = users.find_by_username_norm(conn, normalize_username(username))
    if row is None:
        # 不存在的用户同样计算一次哈希，避免以响应时间区分。
        check_password_hash(_placeholder_hash(), password)
        return None
    if not check_password_hash(row["password_hash"], password) or not row["is_active"]:
        return None
    return row


@cache
def _placeholder_hash():
    return generate_password_hash("placeholder-for-timing")
