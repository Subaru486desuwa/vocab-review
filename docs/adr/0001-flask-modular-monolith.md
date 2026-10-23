# 以 Flask 模块化单体承载四个课程实验

为直接展示课程要求的 Flask 路由、MySQL 查询与后端模型加载，本项目采用一个 Flask 应用、Jinja 页面和 PyMySQL 参数化 SQL；不采用前后端分离、ORM 或独立模型微服务。auth、learning、admin、lab 通过 Blueprint 组织；事务集中在业务调用中，模型是可独立失败的能力。这样保留统一登录、学习记录和答辩入口，同时避免额外部署进程与跨服务一致性成本。
