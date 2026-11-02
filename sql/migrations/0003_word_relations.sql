-- 词对关系（ADR 0004）：按词条连接，word_id_a < word_id_b，同一对词可有多种关系。
CREATE TABLE word_relations (
  id BIGINT NOT NULL AUTO_INCREMENT,
  word_id_a BIGINT NOT NULL,
  word_id_b BIGINT NOT NULL,
  relation_type VARCHAR(16) NOT NULL,
  source VARCHAR(255) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  UNIQUE KEY uq_word_relations_pair_type (word_id_a, word_id_b, relation_type),
  KEY ix_word_relations_word_b (word_id_b),
  CONSTRAINT fk_word_relations_word_a FOREIGN KEY (word_id_a) REFERENCES words (id),
  CONSTRAINT fk_word_relations_word_b FOREIGN KEY (word_id_b) REFERENCES words (id),
  CONSTRAINT ck_word_relations_order CHECK (word_id_a < word_id_b),
  CONSTRAINT ck_word_relations_type CHECK (relation_type IN ('synonym', 'derivation', 'confusable'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
