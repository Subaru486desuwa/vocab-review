-- 例句稳定业务键：重复导入按 example_key 匹配，DL 向量与评价标注按它引用例句。
ALTER TABLE examples
  ADD COLUMN example_key VARCHAR(128) COLLATE utf8mb4_bin NOT NULL AFTER id,
  ADD UNIQUE KEY uq_examples_example_key (example_key);
