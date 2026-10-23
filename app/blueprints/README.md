# HTTP 入口

lab.py 提供 `/lab/hello`；auth.py 提供账户页面、登录/注册/退出、`/api/v1/me` 及 `login_required`/`role_required`；learning.py 提供概览、目标词表、练习页面与接口；admin.py 提供内容导入接口；responses.py 负责 JSON 外壳与错误处理。管理页面与其余 learning 路由后续加入。HTTP 层负责会话、权限、CSRF、字段校验与响应，业务和 SQL 分别进入 services 与 repositories。页面和接口路径以 `docs/api.md` 为准。
