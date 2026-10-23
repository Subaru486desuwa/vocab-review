# HTTP 入口

当前 lab.py 提供 `/lab/hello`。后续按 auth、learning、admin、lab 拆分路由；HTTP 层负责会话、权限、CSRF、字段校验与响应，业务和 SQL 分别进入 services 与 repositories。页面和接口路径以 `docs/api.md` 为准。
