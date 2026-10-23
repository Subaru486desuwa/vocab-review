# 业务逻辑

accounts.py 负责注册校验、密码哈希与登录校验；content_import.py 负责内容包预检、题目版本与单事务写入；practice.py 负责目标词表、组卷与作答事务；grading.py 按题目版本判分；review_rules.py 是 review_rules_v1 纯函数；progress.py 负责复习清单与统计；learning_state.py 按作答事实重建学习状态；recall_model.py 校验、加载实验三制品并推理。后续在此实现练习创建、服务端判分、单一提交事务、规则复习、状态重建、导入预检与两类模型调用。写事务范围由业务调用控制；模型推理和文件读取在学习写事务之外。
