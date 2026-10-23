-- 首版 14 张业务表，字段与约束见 docs/data-model.md。
-- 时间为 UTC DATETIME(6)，由应用的 clock 写入；*_norm 使用二进制排序，避免重音或大小写折叠导致误判重复。

CREATE TABLE users (
  id BIGINT NOT NULL AUTO_INCREMENT,
  username VARCHAR(32) NOT NULL,
  username_norm VARCHAR(32) COLLATE utf8mb4_bin NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(16) NOT NULL DEFAULT 'learner',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  display_timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username_norm (username_norm),
  CONSTRAINT ck_users_role CHECK (role IN ('learner', 'admin'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE wordbooks (
  id BIGINT NOT NULL AUTO_INCREMENT,
  code VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  exam_type VARCHAR(16) NOT NULL,
  name VARCHAR(128) NOT NULL,
  source VARCHAR(255) NOT NULL,
  version VARCHAR(32) COLLATE utf8mb4_bin NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_wordbooks_code_version (code, version),
  KEY ix_wordbooks_exam_type_active (exam_type, is_active),
  CONSTRAINT ck_wordbooks_exam_type CHECK (exam_type IN ('cet6', 'postgraduate', 'ielts')),
  CONSTRAINT ck_wordbooks_source CHECK (source <> '' AND version <> '')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE words (
  id BIGINT NOT NULL AUTO_INCREMENT,
  language VARCHAR(8) NOT NULL DEFAULT 'en',
  lemma VARCHAR(100) NOT NULL,
  lemma_norm VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
  phonetic VARCHAR(100) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  UNIQUE KEY uq_words_language_lemma_norm (language, lemma_norm),
  CONSTRAINT ck_words_language CHECK (language IN ('en'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE word_senses (
  id BIGINT NOT NULL AUTO_INCREMENT,
  word_id BIGINT NOT NULL,
  sense_key VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  part_of_speech VARCHAR(16) NOT NULL,
  definition_zh VARCHAR(255) NOT NULL,
  definition_en VARCHAR(500) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  UNIQUE KEY uq_word_senses_word_sense_key (word_id, sense_key),
  CONSTRAINT fk_word_senses_word FOREIGN KEY (word_id) REFERENCES words (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE wordbook_words (
  wordbook_id BIGINT NOT NULL,
  word_id BIGINT NOT NULL,
  position INT NOT NULL,
  source_note VARCHAR(255) NULL,
  PRIMARY KEY (wordbook_id, word_id),
  KEY ix_wordbook_words_word (word_id),
  CONSTRAINT fk_wordbook_words_wordbook FOREIGN KEY (wordbook_id) REFERENCES wordbooks (id),
  CONSTRAINT fk_wordbook_words_word FOREIGN KEY (word_id) REFERENCES words (id),
  CONSTRAINT ck_wordbook_words_position CHECK (position >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE user_wordbooks (
  user_id BIGINT NOT NULL,
  wordbook_id BIGINT NOT NULL,
  selected_at DATETIME(6) NOT NULL,
  PRIMARY KEY (user_id, wordbook_id),
  KEY ix_user_wordbooks_wordbook (wordbook_id),
  CONSTRAINT fk_user_wordbooks_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_user_wordbooks_wordbook FOREIGN KEY (wordbook_id) REFERENCES wordbooks (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE examples (
  id BIGINT NOT NULL AUTO_INCREMENT,
  sense_id BIGINT NOT NULL,
  text_en VARCHAR(1000) NOT NULL,
  translation_zh VARCHAR(1000) NULL,
  source VARCHAR(255) NOT NULL,
  content_version VARCHAR(32) COLLATE utf8mb4_bin NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (id),
  KEY ix_examples_sense_active (sense_id, is_active),
  CONSTRAINT fk_examples_sense FOREIGN KEY (sense_id) REFERENCES word_senses (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE questions (
  id BIGINT NOT NULL AUTO_INCREMENT,
  logical_key VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
  version INT NOT NULL,
  sense_id BIGINT NOT NULL,
  skill_type VARCHAR(16) NOT NULL,
  prompt VARCHAR(1000) NOT NULL,
  options_json JSON NULL,
  answers_json JSON NOT NULL,
  grading_policy_json JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'published',
  PRIMARY KEY (id),
  UNIQUE KEY uq_questions_logical_key_version (logical_key, version),
  KEY ix_questions_sense_skill_status (sense_id, skill_type, status),
  CONSTRAINT fk_questions_sense FOREIGN KEY (sense_id) REFERENCES word_senses (id),
  CONSTRAINT ck_questions_version CHECK (version >= 1),
  CONSTRAINT ck_questions_skill_type CHECK (skill_type IN ('recognition', 'spelling', 'context')),
  CONSTRAINT ck_questions_status CHECK (status IN ('published', 'retired'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE practice_sessions (
  id BIGINT NOT NULL AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  target_snapshot_json JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  KEY ix_practice_sessions_user_started (user_id, started_at),
  CONSTRAINT fk_practice_sessions_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT ck_practice_sessions_status CHECK (status IN ('active', 'completed', 'abandoned'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE session_items (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_id BIGINT NOT NULL,
  question_id BIGINT NOT NULL,
  position INT NOT NULL,
  issued_at DATETIME(6) NOT NULL,
  submitted_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_session_items_session_position (session_id, position),
  KEY ix_session_items_question (question_id),
  CONSTRAINT fk_session_items_session FOREIGN KEY (session_id) REFERENCES practice_sessions (id),
  CONSTRAINT fk_session_items_question FOREIGN KEY (question_id) REFERENCES questions (id),
  CONSTRAINT ck_session_items_position CHECK (position >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE attempts (
  id BIGINT NOT NULL AUTO_INCREMENT,
  session_item_id BIGINT NOT NULL,
  raw_answer_json JSON NOT NULL,
  normalized_answer VARCHAR(255) NOT NULL,
  is_correct BOOLEAN NOT NULL,
  error_type VARCHAR(16) NULL,
  review_rule_version VARCHAR(32) NOT NULL,
  submitted_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_attempts_session_item (session_item_id),
  CONSTRAINT fk_attempts_session_item FOREIGN KEY (session_item_id) REFERENCES session_items (id),
  CONSTRAINT ck_attempts_error_type CHECK (
    error_type IN ('spelling', 'meaning', 'context', 'unanswered', 'unknown')
  ),
  CONSTRAINT ck_attempts_error_when_wrong CHECK (
    (is_correct AND error_type IS NULL) OR (NOT is_correct AND error_type IS NOT NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE learning_state (
  id BIGINT NOT NULL AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  sense_id BIGINT NOT NULL,
  skill_type VARCHAR(16) NOT NULL,
  seen_count INT NOT NULL DEFAULT 0,
  correct_count INT NOT NULL DEFAULT 0,
  correct_streak INT NOT NULL DEFAULT 0,
  interval_stage TINYINT NOT NULL DEFAULT 0,
  last_attempt_at DATETIME(6) NULL,
  next_review_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_learning_state_user_sense_skill (user_id, sense_id, skill_type),
  KEY ix_learning_state_user_next_review (user_id, next_review_at),
  KEY ix_learning_state_sense (sense_id),
  CONSTRAINT fk_learning_state_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_learning_state_sense FOREIGN KEY (sense_id) REFERENCES word_senses (id),
  CONSTRAINT ck_learning_state_skill_type CHECK (skill_type IN ('recognition', 'spelling', 'context')),
  CONSTRAINT ck_learning_state_counts CHECK (
    correct_count >= 0 AND correct_count <= seen_count AND correct_streak >= 0
    AND correct_streak <= correct_count
  ),
  CONSTRAINT ck_learning_state_interval_stage CHECK (interval_stage BETWEEN 0 AND 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE model_versions (
  id BIGINT NOT NULL AUTO_INCREMENT,
  kind VARCHAR(8) NOT NULL,
  model_code VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  version VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  artifact_sha256 CHAR(64) NOT NULL,
  feature_schema_version VARCHAR(64) NULL,
  metadata_json JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  PRIMARY KEY (id),
  UNIQUE KEY uq_model_versions_code_version (model_code, version),
  CONSTRAINT ck_model_versions_kind CHECK (kind IN ('ml', 'dl')),
  CONSTRAINT ck_model_versions_status CHECK (status IN ('active', 'retired'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE inference_events (
  id BIGINT NOT NULL AUTO_INCREMENT,
  request_id VARCHAR(64) NOT NULL,
  user_id BIGINT NULL,
  model_version_id BIGINT NULL,
  kind VARCHAR(8) NOT NULL,
  source_type VARCHAR(16) NOT NULL,
  input_json JSON NOT NULL,
  output_json JSON NULL,
  status VARCHAR(32) NOT NULL,
  model_time_ms DECIMAL(12, 3) NULL,
  processing_time_ms DECIMAL(12, 3) NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY ix_inference_events_user_created (user_id, created_at),
  KEY ix_inference_events_model_version (model_version_id),
  KEY ix_inference_events_request (request_id),
  CONSTRAINT fk_inference_events_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_inference_events_model_version FOREIGN KEY (model_version_id) REFERENCES model_versions (id),
  CONSTRAINT ck_inference_events_kind CHECK (kind IN ('ml', 'dl')),
  CONSTRAINT ck_inference_events_source_type CHECK (source_type IN ('manual_lab', 'source_test', 'user_history'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
