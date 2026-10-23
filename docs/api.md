# 页面与接口契约

当前已实现 `GET /`、`GET /lab/hello`、`/static/`、`/login`、`/register`、`/dashboard`（占位概览）、`POST /auth/register`、`POST /auth/login`、`POST /auth/logout` 与 `GET /api/v1/me`。其余为完整首版的待实现契约，不是当前可调用的接口。

## 页面

| 路径 | 用途 |
| --- | --- |
| /lab/hello | 实验一文字与静态图片 |
| /login, /register | 账户入口 |
| /dashboard, /wordbooks | 概览与目标选择 |
| /practice, /review | 练习、错词与到期复习 |
| /lab/ml | 回归实验、冷启动与不可用状态 |
| /examples, /admin | 英语例句检索与内容维护 |

页面采用 Jinja；动态练习与检索使用同源 JSON。除明确公开页面外要求登录。用户身份来自会话，客户端 user_id、is_correct 或分数不作为业务事实。

## JSON 与账户操作

| 方法与路径 | 输入 | 行为 |
| --- | --- | --- |
| POST /auth/register | username, password, CSRF | 创建 learner 并登录；用户名 3—32 位字母数字下划线、不区分大小写，密码 8—128 位，不符 422；用户名冲突 409；管理员通过 `flask create-admin` 创建 |
| POST /auth/login | username, password, CSRF | 参数化 SQL 查用户，应用层校验哈希；错误密码、不存在或停用用户统一 401 INVALID_CREDENTIALS；成功后清理旧会话并设置身份，`next` 只接受站内路径 |
| POST /auth/logout | CSRF | 清空会话；GET 返回 405，不改变登录状态 |
| GET /api/v1/me | 会话 | 当前用户 id、username、role、display_timezone；未登录 401 |
| GET /api/v1/wordbooks | 可选 exam_type,page | 启用词表、来源、版本、分页及总数 |
| PUT /api/v1/me/wordbooks | wordbook_ids | 验证全部目标后一次提交；撤销目标不删除历史 |
| POST /api/v1/practice/sessions | 目标词表、题型、count | 校验目标并取题，保存快照并返回 session_id |
| GET /api/v1/practice/sessions/{id} | 路径 ID | 仅本人可读；未作答不返回标准答案 |
| POST /api/v1/practice/items/{id}/answer | answer,CSRF | 服务端判分、幂等重试和单一写事务 |
| GET /api/v1/me/review | 可选目标、题型 | 到期与错题清单；未到期明确时间 |
| GET /api/v1/me/stats | 可选目标、题型 | 真实记录的统计；注明粒度、窗口和分母 |
| POST /api/v1/ml/recall | delta_seconds,history_seen,history_correct,CSRF | manual_lab；status、expected_recall、特征/模型版本、model_time_ms |
| POST /api/v1/examples/search | 英语 text,top_k=1—10,可选目标词表 | 例句 ID、正文、目标词义、cosine_similarity、模型/语料版本 |
| POST /api/v1/admin/import | 约定 CSV 内容，管理员及 CSRF | 先预检后显式提交；行级错误或摘要；单批事务失败回滚 |

所有修改操作校验 CSRF。密码使用 Werkzeug 专用哈希与校验函数，不使用裸 SHA-256。SQL 参数化；按请求管理连接并正确释放，写操作显式提交或回滚。

JSON 响应统一包含 `data`、`error`、`request_id`，`error` 为 `{code, message}`，字段校验失败另含 `fields`；响应头 `X-Request-ID` 与 `request_id` 一致。`/api/` 路径或 JSON 请求返回 JSON，表单请求返回页面（状态码相同）。已用错误码：BAD_REQUEST、UNAUTHENTICATED、INVALID_CREDENTIALS、FORBIDDEN、CSRF_FAILED、USERNAME_TAKEN、VALIDATION_FAILED、PAYLOAD_TOO_LARGE（请求体上限 2 MiB）。状态码：400 格式错误；401 未登录；403 权限/CSRF；404 不存在或不归本人的练习；409 重复冲突；413 超大载荷；422 字段语义/token 上限；503 模型或推理留证不可用。错误不回显连接细节或密钥。

## 作答提交事务

1. 从会话取身份，验证题目实例归属；越权一律 404。
2. 固定顺序锁定 practice_session，再锁定 session_item。
3. 已作答：标准化答案相同返回原结果；不同答案 409 ALREADY_SUBMITTED。练习已完成也允许相同提交重放。
4. 未作答：验证练习状态，读取不可变题目版本，按题型和答案规则判分。
5. 创建或锁定 learning_state 后分配服务端提交时间；写 attempts 与 review_rule_version，并更新学习状态、题目时间和练习完成状态。
6. 一并提交；任一步失败全部回滚。行锁与唯一约束共同处理并发，不能只在 Python 先查后插。重练创建新 session_item。

recognition 提交选项 ID。context 为客观选择或明确可接受答案的填空。spelling 默认清理首尾空白，大小写、英美拼写和词形按题目版本的答案与策略处理，不统一词干化。

error_type 为 spelling、meaning、context、unanswered、unknown；只记录题型和答案能支持的错误类别，不从字符差异推断认知原因。

## 推理留证

推理和文件读取在学习写事务之外。模型缺失或契约不匹配返回 503 MODEL_UNAVAILABLE，基础学习继续可用。成功推理后用短事务保存 inference_events，再返回；日志保存失败返回 503 INFERENCE_LOG_FAILED，不作为成功实验样本。
