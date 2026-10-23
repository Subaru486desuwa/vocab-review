# SQL 数据访问

集中 PyMySQL 参数化查询、连接生命周期和行锁。`db.py` 按请求创建连接（autocommit 关闭、DictCursor、UTC 会话），`transaction()` 供 service 划定事务；查询函数接收 `conn`，不自行提交。`migrations.py` 执行 `sql/migrations/`；`users.py`、`content.py`、`wordbooks.py`、`practice.py`、`progress.py` 分别读写账户、内容、目标词表、练习与统计/重建；作答的加锁顺序写在 `practice.py` 顶部。数据字典见 `docs/data-model.md`。
