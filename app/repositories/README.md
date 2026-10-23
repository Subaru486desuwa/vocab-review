# SQL 数据访问

集中 PyMySQL 参数化查询、连接生命周期和行锁。`db.py` 按请求创建连接（autocommit 关闭、DictCursor、UTC 会话），`transaction()` 供 service 划定事务；查询函数接收 `conn`，不自行提交。`migrations.py` 执行 `sql/migrations/`；`users.py`、`content.py` 分别读写账户与内容。数据字典见 `docs/data-model.md`。
