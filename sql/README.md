# 数据库脚本位置

`migrations/NNNN_<描述>.sql` 按编号由 `flask db upgrade` 执行，版本写入 `schema_migrations`；数据字典见 `docs/data-model.md`。已合并的迁移不再修改，变更追加新文件。每条语句以行尾分号结束，不写存储过程。MySQL DDL 会隐式提交，迁移中途失败时需修正后手动清理目标库。演示内容不放在迁移里，而是由 `flask import-content data/demo/v1` 导入，演示学习者由 `flask seed-demo-user` 创建。
