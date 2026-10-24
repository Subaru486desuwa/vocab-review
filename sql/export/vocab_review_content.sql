-- vocab-review 结构与内容表数据；由 scripts/db_export.sh 生成，内容为项目自编演示 v1。
-- 导入空库后无需再执行 flask db upgrade（schema_migrations 已包含已执行版本）。
-- MySQL dump 10.13  Distrib 8.4.11, for Linux (aarch64)
--
-- Host: localhost    Database: vocab_review
-- ------------------------------------------------------
-- Server version	8.4.11

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `attempts`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `attempts` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_item_id` bigint NOT NULL,
  `raw_answer_json` json NOT NULL,
  `normalized_answer` varchar(255) NOT NULL,
  `is_correct` tinyint(1) NOT NULL,
  `error_type` varchar(16) DEFAULT NULL,
  `review_rule_version` varchar(32) NOT NULL,
  `submitted_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_attempts_session_item` (`session_item_id`),
  CONSTRAINT `fk_attempts_session_item` FOREIGN KEY (`session_item_id`) REFERENCES `session_items` (`id`),
  CONSTRAINT `ck_attempts_error_type` CHECK ((`error_type` in (_utf8mb4'spelling',_utf8mb4'meaning',_utf8mb4'context',_utf8mb4'unanswered',_utf8mb4'unknown'))),
  CONSTRAINT `ck_attempts_error_when_wrong` CHECK ((((0 <> `is_correct`) and (`error_type` is null)) or ((0 = `is_correct`) and (`error_type` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `examples`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `examples` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `example_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `sense_id` bigint NOT NULL,
  `text_en` varchar(1000) NOT NULL,
  `translation_zh` varchar(1000) DEFAULT NULL,
  `source` varchar(255) NOT NULL,
  `content_version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_examples_example_key` (`example_key`),
  KEY `ix_examples_sense_active` (`sense_id`,`is_active`),
  CONSTRAINT `fk_examples_sense` FOREIGN KEY (`sense_id`) REFERENCES `word_senses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `inference_events`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inference_events` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `request_id` varchar(64) NOT NULL,
  `user_id` bigint DEFAULT NULL,
  `model_version_id` bigint DEFAULT NULL,
  `kind` varchar(8) NOT NULL,
  `source_type` varchar(16) NOT NULL,
  `input_json` json NOT NULL,
  `output_json` json DEFAULT NULL,
  `status` varchar(32) NOT NULL,
  `model_time_ms` decimal(12,3) DEFAULT NULL,
  `processing_time_ms` decimal(12,3) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_inference_events_user_created` (`user_id`,`created_at`),
  KEY `ix_inference_events_model_version` (`model_version_id`),
  KEY `ix_inference_events_request` (`request_id`),
  CONSTRAINT `fk_inference_events_model_version` FOREIGN KEY (`model_version_id`) REFERENCES `model_versions` (`id`),
  CONSTRAINT `fk_inference_events_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_inference_events_kind` CHECK ((`kind` in (_utf8mb4'ml',_utf8mb4'dl'))),
  CONSTRAINT `ck_inference_events_source_type` CHECK ((`source_type` in (_utf8mb4'manual_lab',_utf8mb4'source_test',_utf8mb4'user_history')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `learning_state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learning_state` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `sense_id` bigint NOT NULL,
  `skill_type` varchar(16) NOT NULL,
  `seen_count` int NOT NULL DEFAULT '0',
  `correct_count` int NOT NULL DEFAULT '0',
  `correct_streak` int NOT NULL DEFAULT '0',
  `interval_stage` tinyint NOT NULL DEFAULT '0',
  `last_attempt_at` datetime(6) DEFAULT NULL,
  `next_review_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_learning_state_user_sense_skill` (`user_id`,`sense_id`,`skill_type`),
  KEY `ix_learning_state_user_next_review` (`user_id`,`next_review_at`),
  KEY `ix_learning_state_sense` (`sense_id`),
  CONSTRAINT `fk_learning_state_sense` FOREIGN KEY (`sense_id`) REFERENCES `word_senses` (`id`),
  CONSTRAINT `fk_learning_state_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_learning_state_counts` CHECK (((`correct_count` >= 0) and (`correct_count` <= `seen_count`) and (`correct_streak` >= 0) and (`correct_streak` <= `correct_count`))),
  CONSTRAINT `ck_learning_state_interval_stage` CHECK ((`interval_stage` between 0 and 3)),
  CONSTRAINT `ck_learning_state_skill_type` CHECK ((`skill_type` in (_utf8mb4'recognition',_utf8mb4'spelling',_utf8mb4'context')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `model_versions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `model_versions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `kind` varchar(8) NOT NULL,
  `model_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `version` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `artifact_sha256` char(64) NOT NULL,
  `feature_schema_version` varchar(64) DEFAULT NULL,
  `metadata_json` json NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'active',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_model_versions_code_version` (`model_code`,`version`),
  CONSTRAINT `ck_model_versions_kind` CHECK ((`kind` in (_utf8mb4'ml',_utf8mb4'dl'))),
  CONSTRAINT `ck_model_versions_status` CHECK ((`status` in (_utf8mb4'active',_utf8mb4'retired')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practice_sessions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `practice_sessions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `target_snapshot_json` json NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'active',
  `started_at` datetime(6) NOT NULL,
  `finished_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_practice_sessions_user_started` (`user_id`,`started_at`),
  CONSTRAINT `fk_practice_sessions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_practice_sessions_status` CHECK ((`status` in (_utf8mb4'active',_utf8mb4'completed',_utf8mb4'abandoned')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `questions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `logical_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `version` int NOT NULL,
  `sense_id` bigint NOT NULL,
  `skill_type` varchar(16) NOT NULL,
  `prompt` varchar(1000) NOT NULL,
  `options_json` json DEFAULT NULL,
  `answers_json` json NOT NULL,
  `grading_policy_json` json NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'published',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_questions_logical_key_version` (`logical_key`,`version`),
  KEY `ix_questions_sense_skill_status` (`sense_id`,`skill_type`,`status`),
  CONSTRAINT `fk_questions_sense` FOREIGN KEY (`sense_id`) REFERENCES `word_senses` (`id`),
  CONSTRAINT `ck_questions_skill_type` CHECK ((`skill_type` in (_utf8mb4'recognition',_utf8mb4'spelling',_utf8mb4'context'))),
  CONSTRAINT `ck_questions_status` CHECK ((`status` in (_utf8mb4'published',_utf8mb4'retired'))),
  CONSTRAINT `ck_questions_version` CHECK ((`version` >= 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schema_migrations`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `schema_migrations` (
  `version` varchar(128) NOT NULL,
  `applied_at` datetime(6) NOT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `session_items`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `session_items` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` bigint NOT NULL,
  `question_id` bigint NOT NULL,
  `position` int NOT NULL,
  `issued_at` datetime(6) NOT NULL,
  `submitted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_session_items_session_position` (`session_id`,`position`),
  KEY `ix_session_items_question` (`question_id`),
  CONSTRAINT `fk_session_items_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`),
  CONSTRAINT `fk_session_items_session` FOREIGN KEY (`session_id`) REFERENCES `practice_sessions` (`id`),
  CONSTRAINT `ck_session_items_position` CHECK ((`position` >= 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_wordbooks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_wordbooks` (
  `user_id` bigint NOT NULL,
  `wordbook_id` bigint NOT NULL,
  `selected_at` datetime(6) NOT NULL,
  PRIMARY KEY (`user_id`,`wordbook_id`),
  KEY `ix_user_wordbooks_wordbook` (`wordbook_id`),
  CONSTRAINT `fk_user_wordbooks_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_user_wordbooks_wordbook` FOREIGN KEY (`wordbook_id`) REFERENCES `wordbooks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `username` varchar(32) NOT NULL,
  `username_norm` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(16) NOT NULL DEFAULT 'learner',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `display_timezone` varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username_norm` (`username_norm`),
  CONSTRAINT `ck_users_role` CHECK ((`role` in (_utf8mb4'learner',_utf8mb4'admin')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `word_senses`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `word_senses` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `word_id` bigint NOT NULL,
  `sense_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `part_of_speech` varchar(16) NOT NULL,
  `definition_zh` varchar(255) NOT NULL,
  `definition_en` varchar(500) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_word_senses_word_sense_key` (`word_id`,`sense_key`),
  CONSTRAINT `fk_word_senses_word` FOREIGN KEY (`word_id`) REFERENCES `words` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wordbook_words`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wordbook_words` (
  `wordbook_id` bigint NOT NULL,
  `word_id` bigint NOT NULL,
  `position` int NOT NULL,
  `source_note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`wordbook_id`,`word_id`),
  KEY `ix_wordbook_words_word` (`word_id`),
  CONSTRAINT `fk_wordbook_words_word` FOREIGN KEY (`word_id`) REFERENCES `words` (`id`),
  CONSTRAINT `fk_wordbook_words_wordbook` FOREIGN KEY (`wordbook_id`) REFERENCES `wordbooks` (`id`),
  CONSTRAINT `ck_wordbook_words_position` CHECK ((`position` >= 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wordbooks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wordbooks` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `exam_type` varchar(16) NOT NULL,
  `name` varchar(128) NOT NULL,
  `source` varchar(255) NOT NULL,
  `version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_wordbooks_code_version` (`code`,`version`),
  KEY `ix_wordbooks_exam_type_active` (`exam_type`,`is_active`),
  CONSTRAINT `ck_wordbooks_exam_type` CHECK ((`exam_type` in (_utf8mb4'cet6',_utf8mb4'postgraduate',_utf8mb4'ielts'))),
  CONSTRAINT `ck_wordbooks_source` CHECK (((`source` <> _utf8mb4'') and (`version` <> _utf8mb4'')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `words`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `words` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `language` varchar(8) NOT NULL DEFAULT 'en',
  `lemma` varchar(100) NOT NULL,
  `lemma_norm` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `phonetic` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_words_language_lemma_norm` (`language`,`lemma_norm`),
  CONSTRAINT `ck_words_language` CHECK ((`language` = _utf8mb4'en'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
-- MySQL dump 10.13  Distrib 8.4.11, for Linux (aarch64)
--
-- Host: localhost    Database: vocab_review
-- ------------------------------------------------------
-- Server version	8.4.11

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `schema_migrations`
--
-- ORDER BY:  `version`

/*!40000 ALTER TABLE `schema_migrations` DISABLE KEYS */;
INSERT INTO `schema_migrations` (`version`, `applied_at`) VALUES ('0001_initial_schema','2026-10-23 13:15:18.537869');
INSERT INTO `schema_migrations` (`version`, `applied_at`) VALUES ('0002_example_key','2026-10-23 13:41:56.298976');
/*!40000 ALTER TABLE `schema_migrations` ENABLE KEYS */;

--
-- Dumping data for table `wordbooks`
--
-- ORDER BY:  `id`,`code`,`version`

/*!40000 ALTER TABLE `wordbooks` DISABLE KEYS */;
INSERT INTO `wordbooks` (`id`, `code`, `exam_type`, `name`, `source`, `version`, `is_active`, `created_at`) VALUES (4,'cet6-demo','cet6','六级演示词表','项目自编演示 v1（AI 起草，待人工校对）','v1',1,'2026-10-23 13:42:00.248089');
INSERT INTO `wordbooks` (`id`, `code`, `exam_type`, `name`, `source`, `version`, `is_active`, `created_at`) VALUES (5,'postgraduate-demo','postgraduate','考研演示词表','项目自编演示 v1（AI 起草，待人工校对）','v1',1,'2026-10-23 13:42:00.248089');
INSERT INTO `wordbooks` (`id`, `code`, `exam_type`, `name`, `source`, `version`, `is_active`, `created_at`) VALUES (6,'ielts-demo','ielts','雅思演示词表','项目自编演示 v1（AI 起草，待人工校对）','v1',1,'2026-10-23 13:42:00.248089');
/*!40000 ALTER TABLE `wordbooks` ENABLE KEYS */;

--
-- Dumping data for table `words`
--
-- ORDER BY:  `id`,`language`,`lemma_norm`

/*!40000 ALTER TABLE `words` DISABLE KEYS */;
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (71,'en','abandon','abandon',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (72,'en','access','access',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (73,'en','maintain','maintain',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (74,'en','significant','significant',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (75,'en','approach','approach',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (76,'en','issue','issue',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (77,'en','evidence','evidence',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (78,'en','contribute','contribute',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (79,'en','benefit','benefit',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (80,'en','crucial','crucial',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (81,'en','ambiguous','ambiguous',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (82,'en','anticipate','anticipate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (83,'en','compromise','compromise',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (84,'en','consequence','consequence',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (85,'en','deliberate','deliberate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (86,'en','eliminate','eliminate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (87,'en','emerge','emerge',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (88,'en','fragile','fragile',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (89,'en','inevitable','inevitable',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (90,'en','intensify','intensify',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (91,'en','notion','notion',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (92,'en','obscure','obscure',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (93,'en','persist','persist',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (94,'en','reluctant','reluctant',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (95,'en','scatter','scatter',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (96,'en','vulnerable','vulnerable',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (97,'en','withdraw','withdraw',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (98,'en','bank','bank',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (99,'en','fair','fair',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (100,'en','spare','spare',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (101,'en','accumulate','accumulate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (102,'en','allocate','allocate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (103,'en','assume','assume',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (104,'en','coherent','coherent',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (105,'en','conceive','conceive',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (106,'en','controversy','controversy',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (107,'en','decline','decline',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (108,'en','diminish','diminish',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (109,'en','distinguish','distinguish',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (110,'en','exaggerate','exaggerate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (111,'en','fundamental','fundamental',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (112,'en','hypothesis','hypothesis',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (113,'en','implication','implication',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (114,'en','incentive','incentive',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (115,'en','justify','justify',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (116,'en','manipulate','manipulate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (117,'en','preliminary','preliminary',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (118,'en','skeptical','skeptical',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (119,'en','undermine','undermine',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (120,'en','yield','yield',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (121,'en','accommodation','accommodation',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (122,'en','analyse','analyse',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (123,'en','behaviour','behaviour',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (124,'en','colleague','colleague',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (125,'en','commute','commute',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (126,'en','curriculum','curriculum',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (127,'en','deadline','deadline',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (128,'en','environment','environment',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (129,'en','facility','facility',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (130,'en','graduate','graduate',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (131,'en','habitat','habitat',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (132,'en','itinerary','itinerary',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (133,'en','landscape','landscape',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (134,'en','neighbourhood','neighbourhood',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (135,'en','pollution','pollution',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (136,'en','recycle','recycle',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (137,'en','schedule','schedule',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (138,'en','tuition','tuition',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (139,'en','volunteer','volunteer',NULL,1);
INSERT INTO `words` (`id`, `language`, `lemma`, `lemma_norm`, `phonetic`, `is_active`) VALUES (140,'en','organise','organise',NULL,1);
/*!40000 ALTER TABLE `words` ENABLE KEYS */;

--
-- Dumping data for table `word_senses`
--
-- ORDER BY:  `id`,`word_id`,`sense_key`

/*!40000 ALTER TABLE `word_senses` DISABLE KEYS */;
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (80,71,'1','v.','放弃；抛弃','to give up something completely',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (81,72,'1','n.','使用权；接近的机会','the right or chance to use something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (82,73,'1','v.','维持；保持','to keep something at the same level',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (83,74,'1','adj.','重要的；显著的','large or important enough to be noticed',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (84,75,'1','n.','方法；途径','a way of dealing with something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (85,75,'2','v.','接近；靠近','to come nearer to something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (86,76,'1','n.','问题；议题','an important topic that people discuss',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (87,76,'2','v.','发布；发出','to officially give or announce something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (88,77,'1','n.','证据','facts that show something is true',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (89,78,'1','v.','贡献；促成','to give something to help achieve a result',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (90,79,'1','n.','好处；益处','an advantage that something gives you',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (91,80,'1','adj.','至关重要的','extremely important',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (92,81,'1','adj.','模棱两可的；含糊的','having more than one possible meaning',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (93,82,'1','v.','预期；预料','to expect that something will happen',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (94,83,'1','n.','妥协；折中','an agreement in which each side gives up something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (95,84,'1','n.','后果；结果','a result of an action',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (96,85,'1','adj.','故意的；蓄意的','done on purpose',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (97,86,'1','v.','消除；排除','to remove something completely',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (98,87,'1','v.','出现；浮现','to appear or become known',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (99,88,'1','adj.','易碎的；脆弱的','easily broken or damaged',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (100,89,'1','adj.','不可避免的','certain to happen',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (101,90,'1','v.','加强；加剧','to become stronger or more extreme',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (102,91,'1','n.','概念；观念','an idea or belief',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (103,92,'1','adj.','模糊的；难懂的','not clear or difficult to understand',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (104,93,'1','v.','坚持；持续','to continue doing something despite difficulty',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (105,94,'1','adj.','不情愿的；勉强的','not willing to do something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (106,95,'1','v.','散布；撒','to throw or spread things over an area',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (107,96,'1','adj.','易受伤害的；脆弱的','easily hurt or harmed',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (108,97,'1','v.','取（款）；撤回','to take money out of an account; to take back',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (109,98,'1','n.','银行','an organization that keeps and lends money',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (110,98,'2','n.','河岸','the land along the side of a river',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (111,99,'1','adj.','公平的','treating people equally',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (112,99,'2','n.','集市；展览会','an event where people show or sell goods',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (113,100,'1','adj.','空闲的；备用的','not being used; free',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (114,100,'2','v.','抽出（时间）；匀出','to give time or money to someone',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (115,101,'1','v.','积累；积聚','to gradually get more of something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (116,102,'1','v.','分配；拨出','to give something for a particular purpose',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (117,103,'1','v.','假定；设想','to think something is true without proof',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (118,103,'2','v.','承担；担任','to take on a responsibility or role',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (119,104,'1','adj.','连贯的；条理清楚的','clear and logically connected',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (120,105,'1','v.','构想；设想','to form an idea in your mind',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (121,106,'1','n.','争议；争论','public disagreement about something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (122,107,'1','v.','下降；减少','to become smaller or fewer',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (123,107,'2','v.','婉拒；谢绝','to politely refuse',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (124,108,'1','v.','减少；减弱','to become or make less',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (125,109,'1','v.','区分；辨别','to recognize the difference between things',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (126,110,'1','v.','夸大；夸张','to describe something as bigger than it is',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (127,111,'1','adj.','基本的；根本的','forming the base of something',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (128,112,'1','n.','假说；假设','an idea that is tested by research',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (129,113,'1','n.','含意；可能的影响','a possible effect or meaning',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (130,114,'1','n.','激励；动机','something that encourages you to act',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (131,115,'1','v.','证明……正当；为……辩护','to show that something is reasonable',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (132,116,'1','v.','操纵；控制','to control someone or something unfairly',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (133,117,'1','adj.','初步的；预备的','coming before the main part',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (134,118,'1','adj.','怀疑的','doubting that something is true',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (135,119,'1','v.','削弱；暗中破坏','to gradually make something weaker',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (136,120,'1','v.','产出；产生','to produce a result',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (137,120,'2','v.','屈服；让步','to stop resisting',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (138,121,'1','n.','住处；住宿','a place to live or stay',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (139,122,'1','v.','分析','to examine something in detail',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (140,123,'1','n.','行为；举止','the way someone acts',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (141,124,'1','n.','同事','a person you work with',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (142,125,'1','v.','通勤','to travel regularly between home and work',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (143,126,'1','n.','课程（体系）','the subjects taught at a school',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (144,127,'1','n.','截止日期','a time by which something must be done',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (145,128,'1','n.','环境','the natural world around us',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (146,129,'1','n.','设施','a building or equipment for a purpose',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (147,130,'1','v.','毕业','to complete a university degree',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (148,130,'2','n.','毕业生','a person who has finished a degree',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (149,131,'1','n.','栖息地','the natural home of an animal or plant',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (150,132,'1','n.','行程；旅行计划','a plan of a journey',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (151,133,'1','n.','风景；景观','everything you can see in an area of land',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (152,134,'1','n.','街区；社区','an area of a town where people live',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (153,135,'1','n.','污染','harmful substances in air, water or soil',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (154,136,'1','v.','回收利用','to treat waste so it can be used again',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (155,137,'1','n.','日程；时间表','a plan of times for events',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (156,138,'1','n.','学费','money paid for teaching',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (157,139,'1','n.','志愿者','a person who works without being paid',1);
INSERT INTO `word_senses` (`id`, `word_id`, `sense_key`, `part_of_speech`, `definition_zh`, `definition_en`, `is_active`) VALUES (158,140,'1','v.','组织；安排','to plan and arrange an event',1);
/*!40000 ALTER TABLE `word_senses` ENABLE KEYS */;

--
-- Dumping data for table `wordbook_words`
--
-- ORDER BY:  `wordbook_id`,`word_id`

/*!40000 ALTER TABLE `wordbook_words` DISABLE KEYS */;
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,71,1,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,72,2,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,73,3,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,74,4,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,75,5,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,76,6,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,77,7,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,78,8,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,79,9,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,80,10,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,81,11,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,82,12,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,83,13,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,84,14,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,85,15,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,86,16,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,87,17,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,88,18,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,89,19,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,90,20,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,91,21,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,92,22,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,93,23,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,94,24,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,95,25,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,96,26,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,97,27,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,98,28,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,99,29,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (4,100,30,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,71,1,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,72,2,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,73,3,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,74,4,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,75,5,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,76,6,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,77,7,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,78,8,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,79,9,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,80,10,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,101,11,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,102,12,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,103,13,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,104,14,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,105,15,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,106,16,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,107,17,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,108,18,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,109,19,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,110,20,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,111,21,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,112,22,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,113,23,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,114,24,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,115,25,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,116,26,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,117,27,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,118,28,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,119,29,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (5,120,30,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,71,1,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,72,2,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,73,3,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,74,4,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,75,5,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,76,6,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,77,7,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,78,8,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,79,9,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,80,10,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,121,11,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,122,12,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,123,13,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,124,14,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,125,15,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,126,16,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,127,17,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,128,18,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,129,19,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,130,20,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,131,21,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,132,22,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,133,23,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,134,24,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,135,25,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,136,26,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,137,27,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,138,28,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,139,29,NULL);
INSERT INTO `wordbook_words` (`wordbook_id`, `word_id`, `position`, `source_note`) VALUES (6,140,30,NULL);
/*!40000 ALTER TABLE `wordbook_words` ENABLE KEYS */;

--
-- Dumping data for table `examples`
--
-- ORDER BY:  `id`,`example_key`

/*!40000 ALTER TABLE `examples` DISABLE KEYS */;
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (80,'abandon-1-1',80,'Bad weather forced the climbers to abandon their attempt to reach the summit.','恶劣天气迫使登山者放弃了登顶的尝试。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (81,'access-1-1',81,'Every student should have access to the library after class.','每个学生课后都应该能使用图书馆。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (82,'maintain-1-1',82,'It is not easy to maintain a healthy diet during exam season.','考试季保持健康饮食并不容易。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (83,'significant-1-1',83,'The new policy had a significant effect on local businesses.','新政策对当地企业产生了显著影响。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (84,'approach-1-1',84,'We need a fresh approach to the problem of traffic jams.','我们需要用新方法解决交通拥堵问题。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (85,'approach-2-1',85,'Please slow down as you approach the school gate.','接近校门时请减速。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (86,'issue-1-1',86,'Climate change is a global issue that no country can ignore.','气候变化是任何国家都不能忽视的全球问题。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (87,'issue-2-1',87,'The government will issue new guidelines next month.','政府下个月将发布新指南。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (88,'evidence-1-1',88,'There is little evidence that the drug works.','几乎没有证据表明这种药有效。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (89,'contribute-1-1',89,'Everyone in the team is expected to contribute ideas.','团队中每个人都应贡献想法。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (90,'benefit-1-1',90,'The main benefit of the plan is that it saves time.','这个计划的主要好处是节省时间。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (91,'crucial-1-1',91,'Sleep is crucial for memory and learning.','睡眠对记忆和学习至关重要。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (92,'ambiguous-1-1',92,'The instructions were so ambiguous that nobody knew what to do.','说明含糊不清，没人知道该做什么。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (93,'anticipate-1-1',93,'We did not anticipate such a large crowd at the concert.','我们没料到音乐会有这么多人。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (94,'compromise-1-1',94,'After hours of debate, the two sides reached a compromise.','经过数小时辩论，双方达成了妥协。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (95,'consequence-1-1',95,'Losing the job was a direct consequence of his carelessness.','丢掉工作是他粗心大意的直接后果。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (96,'deliberate-1-1',96,'It was not an accident but a deliberate attempt to mislead the public.','这不是意外，而是蓄意误导公众。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (97,'eliminate-1-1',97,'The new design aims to eliminate unnecessary steps.','新设计旨在消除不必要的步骤。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (98,'emerge-1-1',98,'New problems may emerge as the project grows.','随着项目发展可能出现新问题。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (99,'fragile-1-1',99,'Please handle the box carefully; the glass inside is fragile.','请小心搬运箱子，里面的玻璃易碎。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (100,'inevitable-1-1',100,'Some mistakes are inevitable when you learn a new language.','学习新语言时有些错误是不可避免的。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (101,'intensify-1-1',101,'The storm is expected to intensify overnight.','预计风暴将在夜间加剧。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (102,'notion-1-1',102,'The notion that money brings happiness is too simple.','金钱带来幸福的观念过于简单。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (103,'obscure-1-1',103,'The meaning of the old poem remains obscure to most readers.','这首古诗的含义对大多数读者仍然模糊难懂。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (104,'persist-1-1',104,'If you persist in practising every day, you will improve.','如果你坚持每天练习，就会进步。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (105,'reluctant-1-1',105,'She was reluctant to share her notes with others.','她不愿意和别人分享笔记。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (106,'scatter-1-1',106,'The wind began to scatter the leaves across the yard.','风开始把树叶吹散到院子各处。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (107,'vulnerable-1-1',107,'Young children are especially vulnerable to the flu.','幼儿特别容易感染流感。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (108,'withdraw-1-1',108,'You can withdraw money from the machine at any time.','你可以随时从机器上取钱。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (109,'bank-1-1',109,'I need to go to the bank to open an account.','我得去银行开个账户。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (110,'bank-2-1',110,'We had a picnic on the bank of the river.','我们在河岸上野餐。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (111,'fair-1-1',111,'It is not fair to judge people by their looks.','以貌取人是不公平的。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (112,'fair-2-1',112,'The town holds a book fair every spring.','镇上每年春天举办书展。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (113,'spare-1-1',113,'What do you like to do in your spare time?','你空闲时喜欢做什么？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (114,'spare-2-1',114,'Could you spare a few minutes to help me?','你能抽出几分钟帮我吗？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (115,'accumulate-1-1',115,'It takes years to accumulate enough experience in this field.','在这个领域积累足够经验需要数年。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (116,'allocate-1-1',116,'The school decided to allocate more money to science teaching.','学校决定为科学教学拨出更多资金。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (117,'assume-1-1',117,'Don\'t assume that everyone agrees with you.','不要假定每个人都同意你。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (118,'assume-2-1',118,'She will assume responsibility for the new department.','她将负责新部门。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (119,'coherent-1-1',119,'A good essay presents a coherent argument.','好文章提出连贯的论证。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (120,'conceive-1-1',120,'It is hard to conceive of a world without the internet.','很难想象没有互联网的世界。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (121,'controversy-1-1',121,'The new law caused great controversy among scientists.','新法律在科学家中引起了巨大争议。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (122,'decline-1-1',122,'Sales began to decline after the price increase.','涨价后销量开始下降。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (123,'decline-2-1',123,'He had to decline the invitation because he was busy.','他因为忙不得不谢绝邀请。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (124,'diminish-1-1',124,'Nothing could diminish her enthusiasm for research.','没有什么能减弱她对研究的热情。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (125,'distinguish-1-1',125,'Can you distinguish between the two sounds?','你能区分这两个声音吗？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (126,'exaggerate-1-1',126,'Newspapers sometimes exaggerate the danger of rare events.','报纸有时会夸大罕见事件的危险。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (127,'fundamental-1-1',127,'Freedom of speech is a fundamental right.','言论自由是一项基本权利。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (128,'hypothesis-1-1',128,'The experiment was designed to test a hypothesis about memory.','该实验旨在检验一个关于记忆的假说。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (129,'implication-1-1',129,'What is the implication of these results for teachers?','这些结果对教师意味着什么？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (130,'incentive-1-1',130,'Lower taxes give companies an incentive to invest.','降低税收给企业投资的动力。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (131,'justify-1-1',131,'How can you justify spending so much on a phone?','你如何证明在手机上花这么多钱是合理的？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (132,'manipulate-1-1',132,'Some advertisements try to manipulate our emotions.','有些广告试图操纵我们的情绪。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (133,'preliminary-1-1',133,'The preliminary results look promising.','初步结果看起来很有希望。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (134,'skeptical-1-1',134,'Many experts remain skeptical about the claim.','许多专家对这一说法仍持怀疑态度。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (135,'undermine-1-1',135,'Constant criticism can undermine a child\'s confidence.','不断的批评会削弱孩子的自信。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (136,'yield-1-1',136,'This method can yield better results in less time.','这种方法能在更短时间内产生更好的结果。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (137,'yield-2-1',137,'The government refused to yield to public pressure.','政府拒绝向公众压力让步。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (138,'accommodation-1-1',138,'The university helps new students find accommodation near campus.','大学帮助新生在校园附近找到住处。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (139,'analyse-1-1',139,'Researchers will analyse the data next week.','研究人员将在下周分析数据。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (140,'behaviour-1-1',140,'The teacher praised the children for their good behaviour.','老师表扬了孩子们的良好表现。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (141,'colleague-1-1',141,'I often have lunch with a colleague from the marketing team.','我常和市场部的一位同事吃午饭。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (142,'commute-1-1',142,'Many people commute to the city by train every day.','许多人每天乘火车通勤进城。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (143,'curriculum-1-1',143,'Coding has become part of the school curriculum.','编程已经成为学校课程的一部分。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (144,'deadline-1-1',144,'The deadline for the application is next Friday.','申请截止日期是下周五。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (145,'environment-1-1',145,'We should protect the environment for future generations.','我们应为子孙后代保护环境。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (146,'facility-1-1',146,'The new sports facility is open to the public.','新的体育设施向公众开放。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (147,'graduate-1-1',147,'She plans to graduate from university next summer.','她计划明年夏天大学毕业。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (148,'graduate-2-1',148,'Every graduate of the program receives a certificate.','该项目的每位毕业生都会获得证书。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (149,'habitat-1-1',149,'Cutting down forests destroys the natural habitat of many animals.','砍伐森林破坏了许多动物的自然栖息地。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (150,'itinerary-1-1',150,'Our travel agent sent us a detailed itinerary for the trip.','旅行社给我们发来了详细的行程。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (151,'landscape-1-1',151,'The mountain landscape attracts thousands of hikers.','山地风景吸引了成千上万的徒步者。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (152,'neighbourhood-1-1',152,'It is a quiet neighbourhood with many parks.','这是个有很多公园的安静街区。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (153,'pollution-1-1',153,'Air pollution is a serious problem in big cities.','空气污染是大城市的严重问题。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (154,'recycle-1-1',154,'We recycle paper, glass and plastic at home.','我们在家回收纸、玻璃和塑料。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (155,'schedule-1-1',155,'Let me check my schedule before I agree to the meeting.','同意开会前我先查看一下日程。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (156,'tuition-1-1',156,'Many students take part-time jobs to pay their tuition.','许多学生做兼职来支付学费。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (157,'volunteer-1-1',157,'She works as a volunteer at the local hospital.','她在当地医院当志愿者。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (158,'organise-1-1',158,'The students will organise a charity concert.','学生们将组织一场慈善音乐会。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (159,'abandon-1-2',80,'The family had to abandon their car in the deep snow.','一家人不得不把车丢弃在深雪里。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (160,'access-1-2',81,'Many villages still have no access to clean water.','许多村庄仍然无法获得干净的水。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (161,'maintain-1-2',82,'The two countries want to maintain good relations.','两国希望保持良好关系。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (162,'significant-1-2',83,'There has been a significant increase in online shopping.','网购出现了显著增长。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (163,'approach-1-2',84,'Her approach to teaching grammar is practical and clear.','她教语法的方法实用而清晰。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (164,'approach-2-2',85,'A stranger began to approach us in the dark street.','一个陌生人在黑暗的街上开始向我们走近。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (165,'issue-1-2',86,'Housing costs are the main issue for young workers.','住房成本是年轻工人面临的主要问题。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (166,'issue-2-2',87,'The bank will issue new cards to all customers.','银行将向所有客户发放新卡。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (167,'evidence-1-2',88,'The police found no evidence of a break-in.','警方没有发现闯入的证据。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (168,'contribute-1-2',89,'Regular exercise can contribute to better sleep.','规律锻炼有助于改善睡眠。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (169,'benefit-1-2',90,'One benefit of living in the city is easy transport.','住在城市的一个好处是交通便利。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (170,'crucial-1-2',91,'Good communication is crucial in a crisis.','危机中良好的沟通至关重要。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (171,'ambiguous-1-2',92,'His answer was ambiguous, so we asked him again.','他的回答模棱两可，所以我们又问了一遍。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (172,'anticipate-1-2',93,'Engineers try to anticipate problems before they happen.','工程师努力在问题发生前预见它们。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (173,'compromise-1-2',94,'Neither side was willing to make a compromise.','双方都不愿意妥协。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (174,'consequence-1-2',95,'Rising sea levels are one consequence of global warming.','海平面上升是全球变暖的后果之一。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (175,'deliberate-1-2',96,'He told a deliberate lie to protect his friend.','他为了保护朋友故意撒了谎。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (176,'eliminate-1-2',97,'Washing your hands helps eliminate harmful germs.','洗手有助于消除有害细菌。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (177,'emerge-1-2',98,'The sun began to emerge from behind the clouds.','太阳开始从云后露出来。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (178,'fragile-1-2',99,'After the illness, her health remained fragile.','病后她的身体仍然虚弱。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (179,'inevitable-1-2',100,'With so little rain, a water shortage seemed inevitable.','降雨这么少，缺水似乎不可避免。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (180,'intensify-1-2',101,'The police decided to intensify their search.','警方决定加强搜寻。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (181,'notion-1-2',102,'Some people reject the notion that failure is useful.','有些人不接受失败有益这一观念。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (182,'obscure-1-2',103,'The details of the agreement are still obscure.','协议细节仍不清楚。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (183,'persist-1-2',104,'Doctors warned that the symptoms may persist for weeks.','医生警告症状可能持续数周。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (184,'reluctant-1-2',105,'Many shoppers are reluctant to pay more for green products.','许多顾客不愿为环保产品多付钱。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (185,'scatter-1-2',106,'The children began to scatter when the rain started.','下雨时孩子们开始四散跑开。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (186,'vulnerable-1-2',107,'Old computer systems are vulnerable to attacks.','旧计算机系统容易受到攻击。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (187,'withdraw-1-2',108,'The company decided to withdraw its offer.','公司决定撤回报价。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (188,'bank-1-2',109,'She works at a bank in the city centre.','她在市中心的一家银行工作。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (189,'bank-2-2',110,'The boat was tied to the bank near the bridge.','船系在桥附近的岸边。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (190,'fair-1-2',111,'The teacher gave every student a fair chance to speak.','老师给每个学生公平的发言机会。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (191,'fair-2-2',112,'We bought fresh honey at the village fair.','我们在村里的集市上买了新鲜蜂蜜。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (192,'spare-1-2',113,'Always carry a spare key in case you lose yours.','总要带一把备用钥匙，以防丢了自己的。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (193,'spare-2-2',114,'I cannot spare the time to watch the whole film.','我抽不出时间看完整部电影。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (194,'accumulate-1-2',115,'Dust tends to accumulate under the bed.','灰尘容易积在床下。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (195,'allocate-1-2',116,'The manager will allocate tasks to each member.','经理会给每个成员分配任务。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (196,'assume-1-2',117,'We should not assume that the data is correct.','我们不应假定数据是正确的。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (197,'assume-2-2',118,'He will assume the role of team leader next year.','他明年将担任团队负责人。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (198,'coherent-1-2',119,'The report lacks a coherent structure.','这份报告缺乏条理清楚的结构。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (199,'conceive-1-2',120,'Scientists conceive an idea first and then test it.','科学家先构想一个想法，然后加以检验。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (200,'controversy-1-2',121,'The decision to close the library caused controversy.','关闭图书馆的决定引发了争议。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (201,'decline-1-2',122,'The number of birds in the area continues to decline.','该地区鸟类数量持续减少。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (202,'decline-2-2',123,'She chose to decline the job offer from the bank.','她选择婉拒那家银行的工作邀请。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (203,'diminish-1-2',124,'The pain will diminish after a few days.','几天后疼痛会减轻。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (204,'distinguish-1-2',125,'It is hard to distinguish the twins from each other.','很难区分这对双胞胎。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (205,'exaggerate-1-2',126,'Please do not exaggerate the size of the problem.','请不要夸大问题的严重性。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (206,'fundamental-1-2',127,'There is a fundamental difference between the two plans.','两个计划之间存在根本差异。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (207,'hypothesis-1-2',128,'Their hypothesis was supported by the new data.','他们的假说得到了新数据的支持。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (208,'implication-1-2',129,'The implication of his remark was that we had failed.','他话里的意思是我们失败了。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (209,'incentive-1-2',130,'Free meals are an incentive for students to attend.','免费餐是吸引学生参加的激励。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (210,'justify-1-2',131,'The results justify the time we spent on the project.','结果证明我们在项目上花的时间是值得的。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (211,'manipulate-1-2',132,'He was accused of trying to manipulate the election results.','他被指控试图操纵选举结果。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (212,'preliminary-1-2',133,'A preliminary report will be ready next week.','一份初步报告下周就绪。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (213,'skeptical-1-2',134,'I am skeptical about promises of quick weight loss.','我对快速减肥的承诺持怀疑态度。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (214,'undermine-1-2',135,'Rumours can undermine trust within a team.','谣言会削弱团队内部的信任。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (215,'yield-1-2',136,'The new farming method may yield larger harvests.','新的耕作方法可能带来更大的收成。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (216,'yield-2-2',137,'After a long argument, he decided to yield.','经过长时间争论，他决定让步。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (217,'accommodation-1-2',138,'The price includes flights and accommodation.','价格包括机票和住宿。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (218,'analyse-1-2',139,'Students learn to analyse poems in this course.','学生在这门课上学习分析诗歌。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (219,'behaviour-1-2',140,'Scientists study the behaviour of bees in winter.','科学家研究蜜蜂冬季的行为。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (220,'colleague-1-2',141,'My colleague helped me finish the report.','我的同事帮我完成了报告。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (221,'commute-1-2',142,'I commute by bike when the weather is good.','天气好时我骑车通勤。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (222,'curriculum-1-2',143,'The new curriculum includes more science lessons.','新课程包含更多科学课。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (223,'deadline-1-2',144,'We worked late to meet the deadline.','我们加班到很晚以赶上截止日期。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (224,'environment-1-2',145,'Plastic waste is harmful to the environment.','塑料垃圾对环境有害。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (225,'facility-1-2',146,'The hotel has a laundry facility for guests.','酒店为客人提供洗衣设施。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (226,'graduate-1-2',147,'Most students graduate after four years of study.','大多数学生学习四年后毕业。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (227,'graduate-2-2',148,'He is a recent graduate looking for his first job.','他是一名刚毕业、正在找第一份工作的毕业生。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (228,'habitat-1-2',149,'Wetlands provide a habitat for many birds.','湿地为许多鸟类提供栖息地。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (229,'itinerary-1-2',150,'The itinerary includes three days in Rome.','行程包括在罗马的三天。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (230,'landscape-1-2',151,'The landscape changes completely in winter.','冬天景色完全改变。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (231,'neighbourhood-1-2',152,'Our neighbourhood has a small weekly market.','我们街区每周有个小市场。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (232,'pollution-1-2',153,'Noise pollution can affect people\'s health.','噪音污染会影响人们的健康。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (233,'recycle-1-2',154,'Many cities now recycle food waste.','许多城市现在回收利用厨余垃圾。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (234,'schedule-1-2',155,'The train left on schedule despite the snow.','尽管下雪，火车仍按时刻表出发。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (235,'tuition-1-2',156,'The university plans to raise tuition next year.','大学计划明年提高学费。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (236,'volunteer-1-2',157,'Every volunteer received a free T-shirt.','每位志愿者都得到了一件免费 T 恤。','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
INSERT INTO `examples` (`id`, `example_key`, `sense_id`, `text_en`, `translation_zh`, `source`, `content_version`, `is_active`) VALUES (237,'organise-1-2',158,'Can you help me organise my notes?','你能帮我整理笔记吗？','项目自编演示 v1（AI 起草，待人工校对）','demo-v1',1);
/*!40000 ALTER TABLE `examples` ENABLE KEYS */;

--
-- Dumping data for table `questions`
--
-- ORDER BY:  `id`,`logical_key`,`version`

/*!40000 ALTER TABLE `questions` DISABLE KEYS */;
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (238,'abandon-1-recognition',1,80,'recognition','abandon（v.）','[{\"id\": \"a\", \"text\": \"预期；预料\"}, {\"id\": \"b\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"c\", \"text\": \"出现；浮现\"}, {\"id\": \"d\", \"text\": \"放弃；抛弃\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (239,'abandon-1-context',1,80,'context','Bad weather forced the climbers to ____ their attempt to reach the summit.','[{\"id\": \"a\", \"text\": \"emerge\"}, {\"id\": \"b\", \"text\": \"decline\"}, {\"id\": \"c\", \"text\": \"exaggerate\"}, {\"id\": \"d\", \"text\": \"abandon\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (240,'abandon-1-spelling',1,80,'spelling','放弃；抛弃（v.），首字母 a',NULL,'{\"accepted\": [\"abandon\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (241,'access-1-recognition',1,81,'recognition','access（n.）','[{\"id\": \"a\", \"text\": \"方法；途径\"}, {\"id\": \"b\", \"text\": \"学费\"}, {\"id\": \"c\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"d\", \"text\": \"后果；结果\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (242,'access-1-context',1,81,'context','Every student should have ____ to the library after class.','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"volunteer\"}, {\"id\": \"c\", \"text\": \"access\"}, {\"id\": \"d\", \"text\": \"issue\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (243,'access-1-spelling',1,81,'spelling','使用权；接近的机会（n.），首字母 a',NULL,'{\"accepted\": [\"access\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (244,'maintain-1-recognition',1,82,'recognition','maintain（v.）','[{\"id\": \"a\", \"text\": \"维持；保持\"}, {\"id\": \"b\", \"text\": \"承担；担任\"}, {\"id\": \"c\", \"text\": \"夸大；夸张\"}, {\"id\": \"d\", \"text\": \"消除；排除\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (245,'maintain-1-context',1,82,'context','It is not easy to ____ a healthy diet during exam season.','[{\"id\": \"a\", \"text\": \"issue\"}, {\"id\": \"b\", \"text\": \"maintain\"}, {\"id\": \"c\", \"text\": \"anticipate\"}, {\"id\": \"d\", \"text\": \"analyse\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (246,'maintain-1-spelling',1,82,'spelling','维持；保持（v.），首字母 m',NULL,'{\"accepted\": [\"maintain\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (247,'significant-1-recognition',1,83,'recognition','significant（adj.）','[{\"id\": \"a\", \"text\": \"重要的；显著的\"}, {\"id\": \"b\", \"text\": \"易碎的；脆弱的\"}, {\"id\": \"c\", \"text\": \"初步的；预备的\"}, {\"id\": \"d\", \"text\": \"易受伤害的；脆弱的\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (248,'significant-1-context',1,83,'context','The new policy had a ____ effect on local businesses.','[{\"id\": \"a\", \"text\": \"crucial\"}, {\"id\": \"b\", \"text\": \"fundamental\"}, {\"id\": \"c\", \"text\": \"significant\"}, {\"id\": \"d\", \"text\": \"preliminary\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (249,'significant-1-spelling',1,83,'spelling','重要的；显著的（adj.），首字母 s',NULL,'{\"accepted\": [\"significant\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (250,'approach-1-recognition',1,84,'recognition','approach（n.）','[{\"id\": \"a\", \"text\": \"方法；途径\"}, {\"id\": \"b\", \"text\": \"住处；住宿\"}, {\"id\": \"c\", \"text\": \"激励；动机\"}, {\"id\": \"d\", \"text\": \"志愿者\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (251,'approach-1-context',1,84,'context','We need a fresh ____ to the problem of traffic jams.','[{\"id\": \"a\", \"text\": \"bank\"}, {\"id\": \"b\", \"text\": \"approach\"}, {\"id\": \"c\", \"text\": \"habitat\"}, {\"id\": \"d\", \"text\": \"behaviour\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (252,'approach-1-spelling',1,84,'spelling','方法；途径（n.），首字母 a',NULL,'{\"accepted\": [\"approach\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (253,'approach-2-recognition',1,85,'recognition','approach（v.）','[{\"id\": \"a\", \"text\": \"出现；浮现\"}, {\"id\": \"b\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"c\", \"text\": \"接近；靠近\"}, {\"id\": \"d\", \"text\": \"区分；辨别\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (254,'approach-2-context',1,85,'context','Please slow down as you ____ the school gate.','[{\"id\": \"a\", \"text\": \"issue\"}, {\"id\": \"b\", \"text\": \"recycle\"}, {\"id\": \"c\", \"text\": \"approach\"}, {\"id\": \"d\", \"text\": \"allocate\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (255,'approach-2-spelling',1,85,'spelling','接近；靠近（v.），首字母 a',NULL,'{\"accepted\": [\"approach\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (256,'issue-1-recognition',1,86,'recognition','issue（n.）','[{\"id\": \"a\", \"text\": \"设施\"}, {\"id\": \"b\", \"text\": \"问题；议题\"}, {\"id\": \"c\", \"text\": \"志愿者\"}, {\"id\": \"d\", \"text\": \"风景；景观\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (257,'issue-1-context',1,86,'context','Climate change is a global ____ that no country can ignore.','[{\"id\": \"a\", \"text\": \"facility\"}, {\"id\": \"b\", \"text\": \"access\"}, {\"id\": \"c\", \"text\": \"hypothesis\"}, {\"id\": \"d\", \"text\": \"issue\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (258,'issue-1-spelling',1,86,'spelling','问题；议题（n.），首字母 i',NULL,'{\"accepted\": [\"issue\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (259,'issue-2-recognition',1,87,'recognition','issue（v.）','[{\"id\": \"a\", \"text\": \"取（款）；撤回\"}, {\"id\": \"b\", \"text\": \"维持；保持\"}, {\"id\": \"c\", \"text\": \"发布；发出\"}, {\"id\": \"d\", \"text\": \"毕业\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (260,'issue-2-context',1,87,'context','The government will ____ new guidelines next month.','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"issue\"}, {\"id\": \"c\", \"text\": \"diminish\"}, {\"id\": \"d\", \"text\": \"recycle\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (261,'issue-2-spelling',1,87,'spelling','发布；发出（v.），首字母 i',NULL,'{\"accepted\": [\"issue\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (262,'evidence-1-recognition',1,88,'recognition','evidence（n.）','[{\"id\": \"a\", \"text\": \"证据\"}, {\"id\": \"b\", \"text\": \"概念；观念\"}, {\"id\": \"c\", \"text\": \"毕业生\"}, {\"id\": \"d\", \"text\": \"好处；益处\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (263,'evidence-1-context',1,88,'context','There is little ____ that the drug works.','[{\"id\": \"a\", \"text\": \"incentive\"}, {\"id\": \"b\", \"text\": \"issue\"}, {\"id\": \"c\", \"text\": \"hypothesis\"}, {\"id\": \"d\", \"text\": \"evidence\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (264,'evidence-1-spelling',1,88,'spelling','证据（n.），首字母 e',NULL,'{\"accepted\": [\"evidence\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (265,'contribute-1-recognition',1,89,'recognition','contribute（v.）','[{\"id\": \"a\", \"text\": \"贡献；促成\"}, {\"id\": \"b\", \"text\": \"承担；担任\"}, {\"id\": \"c\", \"text\": \"坚持；持续\"}, {\"id\": \"d\", \"text\": \"屈服；让步\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (266,'contribute-1-context',1,89,'context','Everyone in the team is expected to ____ ideas.','[{\"id\": \"a\", \"text\": \"undermine\"}, {\"id\": \"b\", \"text\": \"accumulate\"}, {\"id\": \"c\", \"text\": \"contribute\"}, {\"id\": \"d\", \"text\": \"exaggerate\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (267,'contribute-1-spelling',1,89,'spelling','贡献；促成（v.），首字母 c',NULL,'{\"accepted\": [\"contribute\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (268,'benefit-1-recognition',1,90,'recognition','benefit（n.）','[{\"id\": \"a\", \"text\": \"妥协；折中\"}, {\"id\": \"b\", \"text\": \"好处；益处\"}, {\"id\": \"c\", \"text\": \"河岸\"}, {\"id\": \"d\", \"text\": \"设施\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (269,'benefit-1-context',1,90,'context','The main ____ of the plan is that it saves time.','[{\"id\": \"a\", \"text\": \"implication\"}, {\"id\": \"b\", \"text\": \"benefit\"}, {\"id\": \"c\", \"text\": \"accommodation\"}, {\"id\": \"d\", \"text\": \"volunteer\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (270,'benefit-1-spelling',1,90,'spelling','好处；益处（n.），首字母 b',NULL,'{\"accepted\": [\"benefit\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (271,'crucial-1-recognition',1,91,'recognition','crucial（adj.）','[{\"id\": \"a\", \"text\": \"至关重要的\"}, {\"id\": \"b\", \"text\": \"空闲的；备用的\"}, {\"id\": \"c\", \"text\": \"不情愿的；勉强的\"}, {\"id\": \"d\", \"text\": \"基本的；根本的\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (272,'crucial-1-context',1,91,'context','Sleep is ____ for memory and learning.','[{\"id\": \"a\", \"text\": \"ambiguous\"}, {\"id\": \"b\", \"text\": \"crucial\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"fair\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (273,'crucial-1-spelling',1,91,'spelling','至关重要的（adj.），首字母 c',NULL,'{\"accepted\": [\"crucial\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (274,'ambiguous-1-recognition',1,92,'recognition','ambiguous（adj.）','[{\"id\": \"a\", \"text\": \"不可避免的\"}, {\"id\": \"b\", \"text\": \"不情愿的；勉强的\"}, {\"id\": \"c\", \"text\": \"空闲的；备用的\"}, {\"id\": \"d\", \"text\": \"模棱两可的；含糊的\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (275,'ambiguous-1-context',1,92,'context','The instructions were so ____ that nobody knew what to do.','[{\"id\": \"a\", \"text\": \"ambiguous\"}, {\"id\": \"b\", \"text\": \"crucial\"}, {\"id\": \"c\", \"text\": \"fragile\"}, {\"id\": \"d\", \"text\": \"spare\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (276,'ambiguous-1-spelling',1,92,'spelling','模棱两可的；含糊的（adj.），首字母 a',NULL,'{\"accepted\": [\"ambiguous\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (277,'anticipate-1-recognition',1,93,'recognition','anticipate（v.）','[{\"id\": \"a\", \"text\": \"组织；安排\"}, {\"id\": \"b\", \"text\": \"夸大；夸张\"}, {\"id\": \"c\", \"text\": \"预期；预料\"}, {\"id\": \"d\", \"text\": \"回收利用\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (278,'anticipate-1-context',1,93,'context','We did not ____ such a large crowd at the concert.','[{\"id\": \"a\", \"text\": \"conceive\"}, {\"id\": \"b\", \"text\": \"diminish\"}, {\"id\": \"c\", \"text\": \"organise\"}, {\"id\": \"d\", \"text\": \"anticipate\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (279,'anticipate-1-spelling',1,93,'spelling','预期；预料（v.），首字母 a',NULL,'{\"accepted\": [\"anticipate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (280,'compromise-1-recognition',1,94,'recognition','compromise（n.）','[{\"id\": \"a\", \"text\": \"好处；益处\"}, {\"id\": \"b\", \"text\": \"后果；结果\"}, {\"id\": \"c\", \"text\": \"方法；途径\"}, {\"id\": \"d\", \"text\": \"妥协；折中\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (281,'compromise-1-context',1,94,'context','After hours of debate, the two sides reached a ____.','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"bank\"}, {\"id\": \"c\", \"text\": \"consequence\"}, {\"id\": \"d\", \"text\": \"compromise\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (282,'compromise-1-spelling',1,94,'spelling','妥协；折中（n.），首字母 c',NULL,'{\"accepted\": [\"compromise\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (283,'consequence-1-recognition',1,95,'recognition','consequence（n.）','[{\"id\": \"a\", \"text\": \"后果；结果\"}, {\"id\": \"b\", \"text\": \"方法；途径\"}, {\"id\": \"c\", \"text\": \"同事\"}, {\"id\": \"d\", \"text\": \"志愿者\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (284,'consequence-1-context',1,95,'context','Losing the job was a direct ____ of his carelessness.','[{\"id\": \"a\", \"text\": \"colleague\"}, {\"id\": \"b\", \"text\": \"behaviour\"}, {\"id\": \"c\", \"text\": \"consequence\"}, {\"id\": \"d\", \"text\": \"evidence\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (285,'consequence-1-spelling',1,95,'spelling','后果；结果（n.），首字母 c',NULL,'{\"accepted\": [\"consequence\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (286,'deliberate-1-recognition',1,96,'recognition','deliberate（adj.）','[{\"id\": \"a\", \"text\": \"故意的；蓄意的\"}, {\"id\": \"b\", \"text\": \"空闲的；备用的\"}, {\"id\": \"c\", \"text\": \"公平的\"}, {\"id\": \"d\", \"text\": \"重要的；显著的\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (287,'deliberate-1-context',1,96,'context','It was not an accident but a ____ attempt to mislead the public.','[{\"id\": \"a\", \"text\": \"coherent\"}, {\"id\": \"b\", \"text\": \"deliberate\"}, {\"id\": \"c\", \"text\": \"crucial\"}, {\"id\": \"d\", \"text\": \"fragile\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (288,'deliberate-1-spelling',1,96,'spelling','故意的；蓄意的（adj.），首字母 d',NULL,'{\"accepted\": [\"deliberate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (289,'eliminate-1-recognition',1,97,'recognition','eliminate（v.）','[{\"id\": \"a\", \"text\": \"消除；排除\"}, {\"id\": \"b\", \"text\": \"分析\"}, {\"id\": \"c\", \"text\": \"假定；设想\"}, {\"id\": \"d\", \"text\": \"回收利用\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (290,'eliminate-1-context',1,97,'context','The new design aims to ____ unnecessary steps.','[{\"id\": \"a\", \"text\": \"emerge\"}, {\"id\": \"b\", \"text\": \"anticipate\"}, {\"id\": \"c\", \"text\": \"organise\"}, {\"id\": \"d\", \"text\": \"eliminate\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (291,'eliminate-1-spelling',1,97,'spelling','消除；排除（v.），首字母 e',NULL,'{\"accepted\": [\"eliminate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (292,'emerge-1-recognition',1,98,'recognition','emerge（v.）','[{\"id\": \"a\", \"text\": \"维持；保持\"}, {\"id\": \"b\", \"text\": \"积累；积聚\"}, {\"id\": \"c\", \"text\": \"承担；担任\"}, {\"id\": \"d\", \"text\": \"出现；浮现\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (293,'emerge-1-context',1,98,'context','New problems may ____ as the project grows.','[{\"id\": \"a\", \"text\": \"spare\"}, {\"id\": \"b\", \"text\": \"justify\"}, {\"id\": \"c\", \"text\": \"emerge\"}, {\"id\": \"d\", \"text\": \"contribute\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (294,'emerge-1-spelling',1,98,'spelling','出现；浮现（v.），首字母 e',NULL,'{\"accepted\": [\"emerge\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (295,'fragile-1-recognition',1,99,'recognition','fragile（adj.）','[{\"id\": \"a\", \"text\": \"至关重要的\"}, {\"id\": \"b\", \"text\": \"空闲的；备用的\"}, {\"id\": \"c\", \"text\": \"易碎的；脆弱的\"}, {\"id\": \"d\", \"text\": \"怀疑的\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (296,'fragile-1-context',1,99,'context','Please handle the box carefully; the glass inside is ____.','[{\"id\": \"a\", \"text\": \"fragile\"}, {\"id\": \"b\", \"text\": \"obscure\"}, {\"id\": \"c\", \"text\": \"crucial\"}, {\"id\": \"d\", \"text\": \"reluctant\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (297,'fragile-1-spelling',1,99,'spelling','易碎的；脆弱的（adj.），首字母 f',NULL,'{\"accepted\": [\"fragile\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (298,'inevitable-1-recognition',1,100,'recognition','inevitable（adj.）','[{\"id\": \"a\", \"text\": \"不情愿的；勉强的\"}, {\"id\": \"b\", \"text\": \"不可避免的\"}, {\"id\": \"c\", \"text\": \"故意的；蓄意的\"}, {\"id\": \"d\", \"text\": \"空闲的；备用的\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (299,'inevitable-1-context',1,100,'context','Some mistakes are ____ when you learn a new language.','[{\"id\": \"a\", \"text\": \"significant\"}, {\"id\": \"b\", \"text\": \"preliminary\"}, {\"id\": \"c\", \"text\": \"coherent\"}, {\"id\": \"d\", \"text\": \"inevitable\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (300,'inevitable-1-spelling',1,100,'spelling','不可避免的（adj.），首字母 i',NULL,'{\"accepted\": [\"inevitable\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (301,'intensify-1-recognition',1,101,'recognition','intensify（v.）','[{\"id\": \"a\", \"text\": \"预期；预料\"}, {\"id\": \"b\", \"text\": \"假定；设想\"}, {\"id\": \"c\", \"text\": \"减少；减弱\"}, {\"id\": \"d\", \"text\": \"加强；加剧\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (302,'intensify-1-context',1,101,'context','The storm is expected to ____ overnight.','[{\"id\": \"a\", \"text\": \"analyse\"}, {\"id\": \"b\", \"text\": \"assume\"}, {\"id\": \"c\", \"text\": \"intensify\"}, {\"id\": \"d\", \"text\": \"manipulate\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (303,'intensify-1-spelling',1,101,'spelling','加强；加剧（v.），首字母 i',NULL,'{\"accepted\": [\"intensify\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (304,'notion-1-recognition',1,102,'recognition','notion（n.）','[{\"id\": \"a\", \"text\": \"概念；观念\"}, {\"id\": \"b\", \"text\": \"好处；益处\"}, {\"id\": \"c\", \"text\": \"行为；举止\"}, {\"id\": \"d\", \"text\": \"环境\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (305,'notion-1-context',1,102,'context','The ____ that money brings happiness is too simple.','[{\"id\": \"a\", \"text\": \"implication\"}, {\"id\": \"b\", \"text\": \"notion\"}, {\"id\": \"c\", \"text\": \"curriculum\"}, {\"id\": \"d\", \"text\": \"neighbourhood\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (306,'notion-1-spelling',1,102,'spelling','概念；观念（n.），首字母 n',NULL,'{\"accepted\": [\"notion\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (307,'obscure-1-recognition',1,103,'recognition','obscure（adj.）','[{\"id\": \"a\", \"text\": \"空闲的；备用的\"}, {\"id\": \"b\", \"text\": \"连贯的；条理清楚的\"}, {\"id\": \"c\", \"text\": \"模糊的；难懂的\"}, {\"id\": \"d\", \"text\": \"怀疑的\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (308,'obscure-1-context',1,103,'context','The meaning of the old poem remains ____ to most readers.','[{\"id\": \"a\", \"text\": \"crucial\"}, {\"id\": \"b\", \"text\": \"reluctant\"}, {\"id\": \"c\", \"text\": \"fundamental\"}, {\"id\": \"d\", \"text\": \"obscure\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (309,'obscure-1-spelling',1,103,'spelling','模糊的；难懂的（adj.），首字母 o',NULL,'{\"accepted\": [\"obscure\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (310,'persist-1-recognition',1,104,'recognition','persist（v.）','[{\"id\": \"a\", \"text\": \"操纵；控制\"}, {\"id\": \"b\", \"text\": \"坚持；持续\"}, {\"id\": \"c\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"d\", \"text\": \"减少；减弱\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (311,'persist-1-context',1,104,'context','If you ____ in practising every day, you will improve.','[{\"id\": \"a\", \"text\": \"commute\"}, {\"id\": \"b\", \"text\": \"persist\"}, {\"id\": \"c\", \"text\": \"distinguish\"}, {\"id\": \"d\", \"text\": \"allocate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (312,'persist-1-spelling',1,104,'spelling','坚持；持续（v.），首字母 p',NULL,'{\"accepted\": [\"persist\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (313,'reluctant-1-recognition',1,105,'recognition','reluctant（adj.）','[{\"id\": \"a\", \"text\": \"模糊的；难懂的\"}, {\"id\": \"b\", \"text\": \"空闲的；备用的\"}, {\"id\": \"c\", \"text\": \"模棱两可的；含糊的\"}, {\"id\": \"d\", \"text\": \"不情愿的；勉强的\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (314,'reluctant-1-context',1,105,'context','She was ____ to share her notes with others.','[{\"id\": \"a\", \"text\": \"reluctant\"}, {\"id\": \"b\", \"text\": \"fair\"}, {\"id\": \"c\", \"text\": \"skeptical\"}, {\"id\": \"d\", \"text\": \"fundamental\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (315,'reluctant-1-spelling',1,105,'spelling','不情愿的；勉强的（adj.），首字母 r',NULL,'{\"accepted\": [\"reluctant\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (316,'scatter-1-recognition',1,106,'recognition','scatter（v.）','[{\"id\": \"a\", \"text\": \"分配；拨出\"}, {\"id\": \"b\", \"text\": \"散布；撒\"}, {\"id\": \"c\", \"text\": \"产出；产生\"}, {\"id\": \"d\", \"text\": \"承担；担任\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (317,'scatter-1-context',1,106,'context','The wind began to ____ the leaves across the yard.','[{\"id\": \"a\", \"text\": \"manipulate\"}, {\"id\": \"b\", \"text\": \"scatter\"}, {\"id\": \"c\", \"text\": \"issue\"}, {\"id\": \"d\", \"text\": \"anticipate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (318,'scatter-1-spelling',1,106,'spelling','散布；撒（v.），首字母 s',NULL,'{\"accepted\": [\"scatter\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (319,'vulnerable-1-recognition',1,107,'recognition','vulnerable（adj.）','[{\"id\": \"a\", \"text\": \"易受伤害的；脆弱的\"}, {\"id\": \"b\", \"text\": \"不可避免的\"}, {\"id\": \"c\", \"text\": \"怀疑的\"}, {\"id\": \"d\", \"text\": \"公平的\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (320,'vulnerable-1-context',1,107,'context','Young children are especially ____ to the flu.','[{\"id\": \"a\", \"text\": \"fundamental\"}, {\"id\": \"b\", \"text\": \"inevitable\"}, {\"id\": \"c\", \"text\": \"vulnerable\"}, {\"id\": \"d\", \"text\": \"coherent\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (321,'vulnerable-1-spelling',1,107,'spelling','易受伤害的；脆弱的（adj.），首字母 v',NULL,'{\"accepted\": [\"vulnerable\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (322,'withdraw-1-recognition',1,108,'recognition','withdraw（v.）','[{\"id\": \"a\", \"text\": \"取（款）；撤回\"}, {\"id\": \"b\", \"text\": \"证明……正当；为……辩护\"}, {\"id\": \"c\", \"text\": \"发布；发出\"}, {\"id\": \"d\", \"text\": \"操纵；控制\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (323,'withdraw-1-context',1,108,'context','You can ____ money from the machine at any time.','[{\"id\": \"a\", \"text\": \"accumulate\"}, {\"id\": \"b\", \"text\": \"persist\"}, {\"id\": \"c\", \"text\": \"analyse\"}, {\"id\": \"d\", \"text\": \"withdraw\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (324,'withdraw-1-spelling',1,108,'spelling','取（款）；撤回（v.），首字母 w',NULL,'{\"accepted\": [\"withdraw\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (325,'bank-1-recognition',1,109,'recognition','bank（n.）','[{\"id\": \"a\", \"text\": \"银行\"}, {\"id\": \"b\", \"text\": \"污染\"}, {\"id\": \"c\", \"text\": \"志愿者\"}, {\"id\": \"d\", \"text\": \"方法；途径\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (326,'bank-1-context',1,109,'context','I need to go to the ____ to open an account.','[{\"id\": \"a\", \"text\": \"issue\"}, {\"id\": \"b\", \"text\": \"bank\"}, {\"id\": \"c\", \"text\": \"pollution\"}, {\"id\": \"d\", \"text\": \"environment\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (327,'bank-1-spelling',1,109,'spelling','银行（n.），首字母 b',NULL,'{\"accepted\": [\"bank\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (328,'bank-2-recognition',1,110,'recognition','bank（n.）','[{\"id\": \"a\", \"text\": \"假说；假设\"}, {\"id\": \"b\", \"text\": \"河岸\"}, {\"id\": \"c\", \"text\": \"好处；益处\"}, {\"id\": \"d\", \"text\": \"妥协；折中\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (329,'bank-2-context',1,110,'context','We had a picnic on the ____ of the river.','[{\"id\": \"a\", \"text\": \"colleague\"}, {\"id\": \"b\", \"text\": \"environment\"}, {\"id\": \"c\", \"text\": \"bank\"}, {\"id\": \"d\", \"text\": \"approach\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (330,'bank-2-spelling',1,110,'spelling','河岸（n.），首字母 b',NULL,'{\"accepted\": [\"bank\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (331,'fair-1-recognition',1,111,'recognition','fair（adj.）','[{\"id\": \"a\", \"text\": \"公平的\"}, {\"id\": \"b\", \"text\": \"怀疑的\"}, {\"id\": \"c\", \"text\": \"空闲的；备用的\"}, {\"id\": \"d\", \"text\": \"初步的；预备的\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (332,'fair-1-context',1,111,'context','It is not ____ to judge people by their looks.','[{\"id\": \"a\", \"text\": \"fair\"}, {\"id\": \"b\", \"text\": \"deliberate\"}, {\"id\": \"c\", \"text\": \"preliminary\"}, {\"id\": \"d\", \"text\": \"obscure\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (333,'fair-1-spelling',1,111,'spelling','公平的（adj.），首字母 f',NULL,'{\"accepted\": [\"fair\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (334,'fair-2-recognition',1,112,'recognition','fair（n.）','[{\"id\": \"a\", \"text\": \"污染\"}, {\"id\": \"b\", \"text\": \"集市；展览会\"}, {\"id\": \"c\", \"text\": \"方法；途径\"}, {\"id\": \"d\", \"text\": \"风景；景观\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (335,'fair-2-context',1,112,'context','The town holds a book ____ every spring.','[{\"id\": \"a\", \"text\": \"access\"}, {\"id\": \"b\", \"text\": \"compromise\"}, {\"id\": \"c\", \"text\": \"fair\"}, {\"id\": \"d\", \"text\": \"curriculum\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (336,'fair-2-spelling',1,112,'spelling','集市；展览会（n.），首字母 f',NULL,'{\"accepted\": [\"fair\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (337,'spare-1-recognition',1,113,'recognition','spare（adj.）','[{\"id\": \"a\", \"text\": \"怀疑的\"}, {\"id\": \"b\", \"text\": \"连贯的；条理清楚的\"}, {\"id\": \"c\", \"text\": \"空闲的；备用的\"}, {\"id\": \"d\", \"text\": \"模糊的；难懂的\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (338,'spare-1-context',1,113,'context','What do you like to do in your ____ time?','[{\"id\": \"a\", \"text\": \"skeptical\"}, {\"id\": \"b\", \"text\": \"inevitable\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"obscure\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (339,'spare-1-spelling',1,113,'spelling','空闲的；备用的（adj.），首字母 s',NULL,'{\"accepted\": [\"spare\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (340,'spare-2-recognition',1,114,'recognition','spare（v.）','[{\"id\": \"a\", \"text\": \"构想；设想\"}, {\"id\": \"b\", \"text\": \"抽出（时间）；匀出\"}, {\"id\": \"c\", \"text\": \"操纵；控制\"}, {\"id\": \"d\", \"text\": \"证明……正当；为……辩护\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (341,'spare-2-context',1,114,'context','Could you ____ a few minutes to help me?','[{\"id\": \"a\", \"text\": \"eliminate\"}, {\"id\": \"b\", \"text\": \"exaggerate\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"yield\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (342,'spare-2-spelling',1,114,'spelling','抽出（时间）；匀出（v.），首字母 s',NULL,'{\"accepted\": [\"spare\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (343,'accumulate-1-recognition',1,115,'recognition','accumulate（v.）','[{\"id\": \"a\", \"text\": \"取（款）；撤回\"}, {\"id\": \"b\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"c\", \"text\": \"减少；减弱\"}, {\"id\": \"d\", \"text\": \"积累；积聚\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (344,'accumulate-1-context',1,115,'context','It takes years to ____ enough experience in this field.','[{\"id\": \"a\", \"text\": \"diminish\"}, {\"id\": \"b\", \"text\": \"accumulate\"}, {\"id\": \"c\", \"text\": \"undermine\"}, {\"id\": \"d\", \"text\": \"analyse\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (345,'accumulate-1-spelling',1,115,'spelling','积累；积聚（v.），首字母 a',NULL,'{\"accepted\": [\"accumulate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (346,'allocate-1-recognition',1,116,'recognition','allocate（v.）','[{\"id\": \"a\", \"text\": \"毕业\"}, {\"id\": \"b\", \"text\": \"坚持；持续\"}, {\"id\": \"c\", \"text\": \"分配；拨出\"}, {\"id\": \"d\", \"text\": \"放弃；抛弃\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (347,'allocate-1-context',1,116,'context','The school decided to ____ more money to science teaching.','[{\"id\": \"a\", \"text\": \"allocate\"}, {\"id\": \"b\", \"text\": \"commute\"}, {\"id\": \"c\", \"text\": \"contribute\"}, {\"id\": \"d\", \"text\": \"assume\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (348,'allocate-1-spelling',1,116,'spelling','分配；拨出（v.），首字母 a',NULL,'{\"accepted\": [\"allocate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (349,'assume-1-recognition',1,117,'recognition','assume（v.）','[{\"id\": \"a\", \"text\": \"假定；设想\"}, {\"id\": \"b\", \"text\": \"回收利用\"}, {\"id\": \"c\", \"text\": \"分析\"}, {\"id\": \"d\", \"text\": \"坚持；持续\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (350,'assume-1-context',1,117,'context','Don\'t ____ that everyone agrees with you.','[{\"id\": \"a\", \"text\": \"abandon\"}, {\"id\": \"b\", \"text\": \"assume\"}, {\"id\": \"c\", \"text\": \"conceive\"}, {\"id\": \"d\", \"text\": \"anticipate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (351,'assume-1-spelling',1,117,'spelling','假定；设想（v.），首字母 a',NULL,'{\"accepted\": [\"assume\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (352,'assume-2-recognition',1,118,'recognition','assume（v.）','[{\"id\": \"a\", \"text\": \"接近；靠近\"}, {\"id\": \"b\", \"text\": \"减少；减弱\"}, {\"id\": \"c\", \"text\": \"承担；担任\"}, {\"id\": \"d\", \"text\": \"消除；排除\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (353,'assume-2-context',1,118,'context','She will ____ responsibility for the new department.','[{\"id\": \"a\", \"text\": \"assume\"}, {\"id\": \"b\", \"text\": \"accumulate\"}, {\"id\": \"c\", \"text\": \"commute\"}, {\"id\": \"d\", \"text\": \"distinguish\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (354,'assume-2-spelling',1,118,'spelling','承担；担任（v.），首字母 a',NULL,'{\"accepted\": [\"assume\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (355,'coherent-1-recognition',1,119,'recognition','coherent（adj.）','[{\"id\": \"a\", \"text\": \"易受伤害的；脆弱的\"}, {\"id\": \"b\", \"text\": \"连贯的；条理清楚的\"}, {\"id\": \"c\", \"text\": \"空闲的；备用的\"}, {\"id\": \"d\", \"text\": \"重要的；显著的\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (356,'coherent-1-context',1,119,'context','A good essay presents a ____ argument.','[{\"id\": \"a\", \"text\": \"vulnerable\"}, {\"id\": \"b\", \"text\": \"deliberate\"}, {\"id\": \"c\", \"text\": \"coherent\"}, {\"id\": \"d\", \"text\": \"spare\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (357,'coherent-1-spelling',1,119,'spelling','连贯的；条理清楚的（adj.），首字母 c',NULL,'{\"accepted\": [\"coherent\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (358,'conceive-1-recognition',1,120,'recognition','conceive（v.）','[{\"id\": \"a\", \"text\": \"构想；设想\"}, {\"id\": \"b\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"c\", \"text\": \"放弃；抛弃\"}, {\"id\": \"d\", \"text\": \"抽出（时间）；匀出\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (359,'conceive-1-context',1,120,'context','It is hard to ____ of a world without the internet.','[{\"id\": \"a\", \"text\": \"organise\"}, {\"id\": \"b\", \"text\": \"yield\"}, {\"id\": \"c\", \"text\": \"conceive\"}, {\"id\": \"d\", \"text\": \"graduate\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (360,'conceive-1-spelling',1,120,'spelling','构想；设想（v.），首字母 c',NULL,'{\"accepted\": [\"conceive\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (361,'controversy-1-recognition',1,121,'recognition','controversy（n.）','[{\"id\": \"a\", \"text\": \"课程（体系）\"}, {\"id\": \"b\", \"text\": \"行为；举止\"}, {\"id\": \"c\", \"text\": \"河岸\"}, {\"id\": \"d\", \"text\": \"争议；争论\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (362,'controversy-1-context',1,121,'context','The new law caused great ____ among scientists.','[{\"id\": \"a\", \"text\": \"accommodation\"}, {\"id\": \"b\", \"text\": \"pollution\"}, {\"id\": \"c\", \"text\": \"environment\"}, {\"id\": \"d\", \"text\": \"controversy\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (363,'controversy-1-spelling',1,121,'spelling','争议；争论（n.），首字母 c',NULL,'{\"accepted\": [\"controversy\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (364,'decline-1-recognition',1,122,'recognition','decline（v.）','[{\"id\": \"a\", \"text\": \"积累；积聚\"}, {\"id\": \"b\", \"text\": \"下降；减少\"}, {\"id\": \"c\", \"text\": \"组织；安排\"}, {\"id\": \"d\", \"text\": \"毕业\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (365,'decline-1-context',1,122,'context','Sales began to ____ after the price increase.','[{\"id\": \"a\", \"text\": \"allocate\"}, {\"id\": \"b\", \"text\": \"emerge\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"decline\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (366,'decline-1-spelling',1,122,'spelling','下降；减少（v.），首字母 d',NULL,'{\"accepted\": [\"decline\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (367,'decline-2-recognition',1,123,'recognition','decline（v.）','[{\"id\": \"a\", \"text\": \"预期；预料\"}, {\"id\": \"b\", \"text\": \"坚持；持续\"}, {\"id\": \"c\", \"text\": \"婉拒；谢绝\"}, {\"id\": \"d\", \"text\": \"减少；减弱\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (368,'decline-2-context',1,123,'context','He had to ____ the invitation because he was busy.','[{\"id\": \"a\", \"text\": \"anticipate\"}, {\"id\": \"b\", \"text\": \"decline\"}, {\"id\": \"c\", \"text\": \"contribute\"}, {\"id\": \"d\", \"text\": \"spare\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (369,'decline-2-spelling',1,123,'spelling','婉拒；谢绝（v.），首字母 d',NULL,'{\"accepted\": [\"decline\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (370,'diminish-1-recognition',1,124,'recognition','diminish（v.）','[{\"id\": \"a\", \"text\": \"区分；辨别\"}, {\"id\": \"b\", \"text\": \"发布；发出\"}, {\"id\": \"c\", \"text\": \"减少；减弱\"}, {\"id\": \"d\", \"text\": \"组织；安排\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (371,'diminish-1-context',1,124,'context','Nothing could ____ her enthusiasm for research.','[{\"id\": \"a\", \"text\": \"diminish\"}, {\"id\": \"b\", \"text\": \"distinguish\"}, {\"id\": \"c\", \"text\": \"graduate\"}, {\"id\": \"d\", \"text\": \"accumulate\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (372,'diminish-1-spelling',1,124,'spelling','减少；减弱（v.），首字母 d',NULL,'{\"accepted\": [\"diminish\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (373,'distinguish-1-recognition',1,125,'recognition','distinguish（v.）','[{\"id\": \"a\", \"text\": \"回收利用\"}, {\"id\": \"b\", \"text\": \"分配；拨出\"}, {\"id\": \"c\", \"text\": \"减少；减弱\"}, {\"id\": \"d\", \"text\": \"区分；辨别\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (374,'distinguish-1-context',1,125,'context','Can you ____ between the two sounds?','[{\"id\": \"a\", \"text\": \"conceive\"}, {\"id\": \"b\", \"text\": \"distinguish\"}, {\"id\": \"c\", \"text\": \"withdraw\"}, {\"id\": \"d\", \"text\": \"manipulate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (375,'distinguish-1-spelling',1,125,'spelling','区分；辨别（v.），首字母 d',NULL,'{\"accepted\": [\"distinguish\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (376,'exaggerate-1-recognition',1,126,'recognition','exaggerate（v.）','[{\"id\": \"a\", \"text\": \"加强；加剧\"}, {\"id\": \"b\", \"text\": \"夸大；夸张\"}, {\"id\": \"c\", \"text\": \"消除；排除\"}, {\"id\": \"d\", \"text\": \"婉拒；谢绝\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (377,'exaggerate-1-context',1,126,'context','Newspapers sometimes ____ the danger of rare events.','[{\"id\": \"a\", \"text\": \"exaggerate\"}, {\"id\": \"b\", \"text\": \"diminish\"}, {\"id\": \"c\", \"text\": \"distinguish\"}, {\"id\": \"d\", \"text\": \"assume\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (378,'exaggerate-1-spelling',1,126,'spelling','夸大；夸张（v.），首字母 e',NULL,'{\"accepted\": [\"exaggerate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (379,'fundamental-1-recognition',1,127,'recognition','fundamental（adj.）','[{\"id\": \"a\", \"text\": \"初步的；预备的\"}, {\"id\": \"b\", \"text\": \"基本的；根本的\"}, {\"id\": \"c\", \"text\": \"故意的；蓄意的\"}, {\"id\": \"d\", \"text\": \"模棱两可的；含糊的\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (380,'fundamental-1-context',1,127,'context','Freedom of speech is a ____ right.','[{\"id\": \"a\", \"text\": \"coherent\"}, {\"id\": \"b\", \"text\": \"fundamental\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"crucial\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (381,'fundamental-1-spelling',1,127,'spelling','基本的；根本的（adj.），首字母 f',NULL,'{\"accepted\": [\"fundamental\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (382,'hypothesis-1-recognition',1,128,'recognition','hypothesis（n.）','[{\"id\": \"a\", \"text\": \"学费\"}, {\"id\": \"b\", \"text\": \"假说；假设\"}, {\"id\": \"c\", \"text\": \"激励；动机\"}, {\"id\": \"d\", \"text\": \"后果；结果\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (383,'hypothesis-1-context',1,128,'context','The experiment was designed to test a ____ about memory.','[{\"id\": \"a\", \"text\": \"colleague\"}, {\"id\": \"b\", \"text\": \"hypothesis\"}, {\"id\": \"c\", \"text\": \"consequence\"}, {\"id\": \"d\", \"text\": \"curriculum\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (384,'hypothesis-1-spelling',1,128,'spelling','假说；假设（n.），首字母 h',NULL,'{\"accepted\": [\"hypothesis\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (385,'implication-1-recognition',1,129,'recognition','implication（n.）','[{\"id\": \"a\", \"text\": \"银行\"}, {\"id\": \"b\", \"text\": \"概念；观念\"}, {\"id\": \"c\", \"text\": \"含意；可能的影响\"}, {\"id\": \"d\", \"text\": \"污染\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (386,'implication-1-context',1,129,'context','What is the ____ of these results for teachers?','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"evidence\"}, {\"id\": \"c\", \"text\": \"implication\"}, {\"id\": \"d\", \"text\": \"hypothesis\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (387,'implication-1-spelling',1,129,'spelling','含意；可能的影响（n.），首字母 i',NULL,'{\"accepted\": [\"implication\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (388,'incentive-1-recognition',1,130,'recognition','incentive（n.）','[{\"id\": \"a\", \"text\": \"志愿者\"}, {\"id\": \"b\", \"text\": \"截止日期\"}, {\"id\": \"c\", \"text\": \"毕业生\"}, {\"id\": \"d\", \"text\": \"激励；动机\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (389,'incentive-1-context',1,130,'context','Lower taxes give companies an ____ to invest.','[{\"id\": \"a\", \"text\": \"evidence\"}, {\"id\": \"b\", \"text\": \"approach\"}, {\"id\": \"c\", \"text\": \"incentive\"}, {\"id\": \"d\", \"text\": \"accommodation\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (390,'incentive-1-spelling',1,130,'spelling','激励；动机（n.），首字母 i',NULL,'{\"accepted\": [\"incentive\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (391,'justify-1-recognition',1,131,'recognition','justify（v.）','[{\"id\": \"a\", \"text\": \"分析\"}, {\"id\": \"b\", \"text\": \"证明……正当；为……辩护\"}, {\"id\": \"c\", \"text\": \"婉拒；谢绝\"}, {\"id\": \"d\", \"text\": \"散布；撒\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (392,'justify-1-context',1,131,'context','How can you ____ spending so much on a phone?','[{\"id\": \"a\", \"text\": \"justify\"}, {\"id\": \"b\", \"text\": \"conceive\"}, {\"id\": \"c\", \"text\": \"intensify\"}, {\"id\": \"d\", \"text\": \"assume\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (393,'justify-1-spelling',1,131,'spelling','证明……正当；为……辩护（v.），首字母 j',NULL,'{\"accepted\": [\"justify\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (394,'manipulate-1-recognition',1,132,'recognition','manipulate（v.）','[{\"id\": \"a\", \"text\": \"回收利用\"}, {\"id\": \"b\", \"text\": \"操纵；控制\"}, {\"id\": \"c\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"d\", \"text\": \"承担；担任\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (395,'manipulate-1-context',1,132,'context','Some advertisements try to ____ our emotions.','[{\"id\": \"a\", \"text\": \"manipulate\"}, {\"id\": \"b\", \"text\": \"persist\"}, {\"id\": \"c\", \"text\": \"maintain\"}, {\"id\": \"d\", \"text\": \"justify\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (396,'manipulate-1-spelling',1,132,'spelling','操纵；控制（v.），首字母 m',NULL,'{\"accepted\": [\"manipulate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (397,'preliminary-1-recognition',1,133,'recognition','preliminary（adj.）','[{\"id\": \"a\", \"text\": \"模棱两可的；含糊的\"}, {\"id\": \"b\", \"text\": \"初步的；预备的\"}, {\"id\": \"c\", \"text\": \"易受伤害的；脆弱的\"}, {\"id\": \"d\", \"text\": \"易碎的；脆弱的\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (398,'preliminary-1-context',1,133,'context','The ____ results look promising.','[{\"id\": \"a\", \"text\": \"ambiguous\"}, {\"id\": \"b\", \"text\": \"preliminary\"}, {\"id\": \"c\", \"text\": \"fragile\"}, {\"id\": \"d\", \"text\": \"skeptical\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (399,'preliminary-1-spelling',1,133,'spelling','初步的；预备的（adj.），首字母 p',NULL,'{\"accepted\": [\"preliminary\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (400,'skeptical-1-recognition',1,134,'recognition','skeptical（adj.）','[{\"id\": \"a\", \"text\": \"至关重要的\"}, {\"id\": \"b\", \"text\": \"怀疑的\"}, {\"id\": \"c\", \"text\": \"不可避免的\"}, {\"id\": \"d\", \"text\": \"初步的；预备的\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (401,'skeptical-1-context',1,134,'context','Many experts remain ____ about the claim.','[{\"id\": \"a\", \"text\": \"skeptical\"}, {\"id\": \"b\", \"text\": \"obscure\"}, {\"id\": \"c\", \"text\": \"reluctant\"}, {\"id\": \"d\", \"text\": \"vulnerable\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (402,'skeptical-1-spelling',1,134,'spelling','怀疑的（adj.），首字母 s',NULL,'{\"accepted\": [\"skeptical\", \"sceptical\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (403,'undermine-1-recognition',1,135,'recognition','undermine（v.）','[{\"id\": \"a\", \"text\": \"下降；减少\"}, {\"id\": \"b\", \"text\": \"削弱；暗中破坏\"}, {\"id\": \"c\", \"text\": \"积累；积聚\"}, {\"id\": \"d\", \"text\": \"接近；靠近\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (404,'undermine-1-context',1,135,'context','Constant criticism can ____ a child\'s confidence.','[{\"id\": \"a\", \"text\": \"diminish\"}, {\"id\": \"b\", \"text\": \"assume\"}, {\"id\": \"c\", \"text\": \"spare\"}, {\"id\": \"d\", \"text\": \"undermine\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (405,'undermine-1-spelling',1,135,'spelling','削弱；暗中破坏（v.），首字母 u',NULL,'{\"accepted\": [\"undermine\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (406,'yield-1-recognition',1,136,'recognition','yield（v.）','[{\"id\": \"a\", \"text\": \"毕业\"}, {\"id\": \"b\", \"text\": \"发布；发出\"}, {\"id\": \"c\", \"text\": \"产出；产生\"}, {\"id\": \"d\", \"text\": \"夸大；夸张\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (407,'yield-1-context',1,136,'context','This method can ____ better results in less time.','[{\"id\": \"a\", \"text\": \"persist\"}, {\"id\": \"b\", \"text\": \"scatter\"}, {\"id\": \"c\", \"text\": \"withdraw\"}, {\"id\": \"d\", \"text\": \"yield\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (408,'yield-1-spelling',1,136,'spelling','产出；产生（v.），首字母 y',NULL,'{\"accepted\": [\"yield\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (409,'yield-2-recognition',1,137,'recognition','yield（v.）','[{\"id\": \"a\", \"text\": \"屈服；让步\"}, {\"id\": \"b\", \"text\": \"减少；减弱\"}, {\"id\": \"c\", \"text\": \"回收利用\"}, {\"id\": \"d\", \"text\": \"贡献；促成\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (410,'yield-2-context',1,137,'context','The government refused to ____ to public pressure.','[{\"id\": \"a\", \"text\": \"yield\"}, {\"id\": \"b\", \"text\": \"eliminate\"}, {\"id\": \"c\", \"text\": \"anticipate\"}, {\"id\": \"d\", \"text\": \"assume\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (411,'yield-2-spelling',1,137,'spelling','屈服；让步（v.），首字母 y',NULL,'{\"accepted\": [\"yield\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (412,'accommodation-1-recognition',1,138,'recognition','accommodation（n.）','[{\"id\": \"a\", \"text\": \"志愿者\"}, {\"id\": \"b\", \"text\": \"环境\"}, {\"id\": \"c\", \"text\": \"同事\"}, {\"id\": \"d\", \"text\": \"住处；住宿\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (413,'accommodation-1-context',1,138,'context','The university helps new students find ____ near campus.','[{\"id\": \"a\", \"text\": \"issue\"}, {\"id\": \"b\", \"text\": \"accommodation\"}, {\"id\": \"c\", \"text\": \"controversy\"}, {\"id\": \"d\", \"text\": \"access\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (414,'accommodation-1-spelling',1,138,'spelling','住处；住宿（n.），首字母 a',NULL,'{\"accepted\": [\"accommodation\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (415,'analyse-1-recognition',1,139,'recognition','analyse（v.）','[{\"id\": \"a\", \"text\": \"坚持；持续\"}, {\"id\": \"b\", \"text\": \"分析\"}, {\"id\": \"c\", \"text\": \"分配；拨出\"}, {\"id\": \"d\", \"text\": \"屈服；让步\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (416,'analyse-1-context',1,139,'context','Researchers will ____ the data next week.','[{\"id\": \"a\", \"text\": \"organise\"}, {\"id\": \"b\", \"text\": \"analyse\"}, {\"id\": \"c\", \"text\": \"manipulate\"}, {\"id\": \"d\", \"text\": \"undermine\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (417,'analyse-1-spelling',1,139,'spelling','分析（v.），首字母 a',NULL,'{\"accepted\": [\"analyse\", \"analyze\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (418,'behaviour-1-recognition',1,140,'recognition','behaviour（n.）','[{\"id\": \"a\", \"text\": \"行为；举止\"}, {\"id\": \"b\", \"text\": \"银行\"}, {\"id\": \"c\", \"text\": \"激励；动机\"}, {\"id\": \"d\", \"text\": \"证据\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (419,'behaviour-1-context',1,140,'context','The teacher praised the children for their good ____.','[{\"id\": \"a\", \"text\": \"behaviour\"}, {\"id\": \"b\", \"text\": \"accommodation\"}, {\"id\": \"c\", \"text\": \"schedule\"}, {\"id\": \"d\", \"text\": \"incentive\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (420,'behaviour-1-spelling',1,140,'spelling','行为；举止（n.），首字母 b',NULL,'{\"accepted\": [\"behaviour\", \"behavior\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (421,'colleague-1-recognition',1,141,'recognition','colleague（n.）','[{\"id\": \"a\", \"text\": \"概念；观念\"}, {\"id\": \"b\", \"text\": \"同事\"}, {\"id\": \"c\", \"text\": \"日程；时间表\"}, {\"id\": \"d\", \"text\": \"学费\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (422,'colleague-1-context',1,141,'context','I often have lunch with a ____ from the marketing team.','[{\"id\": \"a\", \"text\": \"colleague\"}, {\"id\": \"b\", \"text\": \"neighbourhood\"}, {\"id\": \"c\", \"text\": \"behaviour\"}, {\"id\": \"d\", \"text\": \"consequence\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (423,'colleague-1-spelling',1,141,'spelling','同事（n.），首字母 c',NULL,'{\"accepted\": [\"colleague\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (424,'commute-1-recognition',1,142,'recognition','commute（v.）','[{\"id\": \"a\", \"text\": \"贡献；促成\"}, {\"id\": \"b\", \"text\": \"证明……正当；为……辩护\"}, {\"id\": \"c\", \"text\": \"散布；撒\"}, {\"id\": \"d\", \"text\": \"通勤\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (425,'commute-1-context',1,142,'context','Many people ____ to the city by train every day.','[{\"id\": \"a\", \"text\": \"scatter\"}, {\"id\": \"b\", \"text\": \"commute\"}, {\"id\": \"c\", \"text\": \"exaggerate\"}, {\"id\": \"d\", \"text\": \"allocate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (426,'commute-1-spelling',1,142,'spelling','通勤（v.），首字母 c',NULL,'{\"accepted\": [\"commute\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (427,'curriculum-1-recognition',1,143,'recognition','curriculum（n.）','[{\"id\": \"a\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"b\", \"text\": \"课程（体系）\"}, {\"id\": \"c\", \"text\": \"同事\"}, {\"id\": \"d\", \"text\": \"集市；展览会\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (428,'curriculum-1-context',1,143,'context','Coding has become part of the school ____.','[{\"id\": \"a\", \"text\": \"itinerary\"}, {\"id\": \"b\", \"text\": \"curriculum\"}, {\"id\": \"c\", \"text\": \"issue\"}, {\"id\": \"d\", \"text\": \"neighbourhood\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (429,'curriculum-1-spelling',1,143,'spelling','课程（体系）（n.），首字母 c',NULL,'{\"accepted\": [\"curriculum\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (430,'deadline-1-recognition',1,144,'recognition','deadline（n.）','[{\"id\": \"a\", \"text\": \"截止日期\"}, {\"id\": \"b\", \"text\": \"证据\"}, {\"id\": \"c\", \"text\": \"街区；社区\"}, {\"id\": \"d\", \"text\": \"银行\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (431,'deadline-1-context',1,144,'context','The ____ for the application is next Friday.','[{\"id\": \"a\", \"text\": \"controversy\"}, {\"id\": \"b\", \"text\": \"deadline\"}, {\"id\": \"c\", \"text\": \"consequence\"}, {\"id\": \"d\", \"text\": \"itinerary\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (432,'deadline-1-spelling',1,144,'spelling','截止日期（n.），首字母 d',NULL,'{\"accepted\": [\"deadline\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (433,'environment-1-recognition',1,145,'recognition','environment（n.）','[{\"id\": \"a\", \"text\": \"好处；益处\"}, {\"id\": \"b\", \"text\": \"环境\"}, {\"id\": \"c\", \"text\": \"银行\"}, {\"id\": \"d\", \"text\": \"毕业生\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (434,'environment-1-context',1,145,'context','We should protect the ____ for future generations.','[{\"id\": \"a\", \"text\": \"hypothesis\"}, {\"id\": \"b\", \"text\": \"implication\"}, {\"id\": \"c\", \"text\": \"approach\"}, {\"id\": \"d\", \"text\": \"environment\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (435,'environment-1-spelling',1,145,'spelling','环境（n.），首字母 e',NULL,'{\"accepted\": [\"environment\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (436,'facility-1-recognition',1,146,'recognition','facility（n.）','[{\"id\": \"a\", \"text\": \"风景；景观\"}, {\"id\": \"b\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"c\", \"text\": \"设施\"}, {\"id\": \"d\", \"text\": \"河岸\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (437,'facility-1-context',1,146,'context','The new sports ____ is open to the public.','[{\"id\": \"a\", \"text\": \"deadline\"}, {\"id\": \"b\", \"text\": \"pollution\"}, {\"id\": \"c\", \"text\": \"hypothesis\"}, {\"id\": \"d\", \"text\": \"facility\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (438,'facility-1-spelling',1,146,'spelling','设施（n.），首字母 f',NULL,'{\"accepted\": [\"facility\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (439,'graduate-1-recognition',1,147,'recognition','graduate（v.）','[{\"id\": \"a\", \"text\": \"操纵；控制\"}, {\"id\": \"b\", \"text\": \"婉拒；谢绝\"}, {\"id\": \"c\", \"text\": \"毕业\"}, {\"id\": \"d\", \"text\": \"承担；担任\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (440,'graduate-1-context',1,147,'context','She plans to ____ from university next summer.','[{\"id\": \"a\", \"text\": \"approach\"}, {\"id\": \"b\", \"text\": \"intensify\"}, {\"id\": \"c\", \"text\": \"graduate\"}, {\"id\": \"d\", \"text\": \"scatter\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (441,'graduate-1-spelling',1,147,'spelling','毕业（v.），首字母 g',NULL,'{\"accepted\": [\"graduate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (442,'graduate-2-recognition',1,148,'recognition','graduate（n.）','[{\"id\": \"a\", \"text\": \"河岸\"}, {\"id\": \"b\", \"text\": \"学费\"}, {\"id\": \"c\", \"text\": \"设施\"}, {\"id\": \"d\", \"text\": \"毕业生\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (443,'graduate-2-context',1,148,'context','Every ____ of the program receives a certificate.','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"bank\"}, {\"id\": \"c\", \"text\": \"fair\"}, {\"id\": \"d\", \"text\": \"controversy\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (444,'graduate-2-spelling',1,148,'spelling','毕业生（n.），首字母 g',NULL,'{\"accepted\": [\"graduate\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (445,'habitat-1-recognition',1,149,'recognition','habitat（n.）','[{\"id\": \"a\", \"text\": \"街区；社区\"}, {\"id\": \"b\", \"text\": \"设施\"}, {\"id\": \"c\", \"text\": \"栖息地\"}, {\"id\": \"d\", \"text\": \"后果；结果\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (446,'habitat-1-context',1,149,'context','Cutting down forests destroys the natural ____ of many animals.','[{\"id\": \"a\", \"text\": \"graduate\"}, {\"id\": \"b\", \"text\": \"habitat\"}, {\"id\": \"c\", \"text\": \"compromise\"}, {\"id\": \"d\", \"text\": \"schedule\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (447,'habitat-1-spelling',1,149,'spelling','栖息地（n.），首字母 h',NULL,'{\"accepted\": [\"habitat\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (448,'itinerary-1-recognition',1,150,'recognition','itinerary（n.）','[{\"id\": \"a\", \"text\": \"志愿者\"}, {\"id\": \"b\", \"text\": \"行程；旅行计划\"}, {\"id\": \"c\", \"text\": \"同事\"}, {\"id\": \"d\", \"text\": \"含意；可能的影响\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (449,'itinerary-1-context',1,150,'context','Our travel agent sent us a detailed ____ for the trip.','[{\"id\": \"a\", \"text\": \"consequence\"}, {\"id\": \"b\", \"text\": \"behaviour\"}, {\"id\": \"c\", \"text\": \"itinerary\"}, {\"id\": \"d\", \"text\": \"access\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (450,'itinerary-1-spelling',1,150,'spelling','行程；旅行计划（n.），首字母 i',NULL,'{\"accepted\": [\"itinerary\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (451,'landscape-1-recognition',1,151,'recognition','landscape（n.）','[{\"id\": \"a\", \"text\": \"风景；景观\"}, {\"id\": \"b\", \"text\": \"证据\"}, {\"id\": \"c\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"d\", \"text\": \"截止日期\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (452,'landscape-1-context',1,151,'context','The mountain ____ attracts thousands of hikers.','[{\"id\": \"a\", \"text\": \"schedule\"}, {\"id\": \"b\", \"text\": \"benefit\"}, {\"id\": \"c\", \"text\": \"landscape\"}, {\"id\": \"d\", \"text\": \"accommodation\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (453,'landscape-1-spelling',1,151,'spelling','风景；景观（n.），首字母 l',NULL,'{\"accepted\": [\"landscape\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (454,'neighbourhood-1-recognition',1,152,'recognition','neighbourhood（n.）','[{\"id\": \"a\", \"text\": \"街区；社区\"}, {\"id\": \"b\", \"text\": \"设施\"}, {\"id\": \"c\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"d\", \"text\": \"激励；动机\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (455,'neighbourhood-1-context',1,152,'context','It is a quiet ____ with many parks.','[{\"id\": \"a\", \"text\": \"evidence\"}, {\"id\": \"b\", \"text\": \"fair\"}, {\"id\": \"c\", \"text\": \"itinerary\"}, {\"id\": \"d\", \"text\": \"neighbourhood\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (456,'neighbourhood-1-spelling',1,152,'spelling','街区；社区（n.），首字母 n',NULL,'{\"accepted\": [\"neighbourhood\", \"neighborhood\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (457,'pollution-1-recognition',1,153,'recognition','pollution（n.）','[{\"id\": \"a\", \"text\": \"后果；结果\"}, {\"id\": \"b\", \"text\": \"污染\"}, {\"id\": \"c\", \"text\": \"截止日期\"}, {\"id\": \"d\", \"text\": \"使用权；接近的机会\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (458,'pollution-1-context',1,153,'context','Air ____ is a serious problem in big cities.','[{\"id\": \"a\", \"text\": \"evidence\"}, {\"id\": \"b\", \"text\": \"landscape\"}, {\"id\": \"c\", \"text\": \"pollution\"}, {\"id\": \"d\", \"text\": \"hypothesis\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (459,'pollution-1-spelling',1,153,'spelling','污染（n.），首字母 p',NULL,'{\"accepted\": [\"pollution\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (460,'recycle-1-recognition',1,154,'recognition','recycle（v.）','[{\"id\": \"a\", \"text\": \"夸大；夸张\"}, {\"id\": \"b\", \"text\": \"抽出（时间）；匀出\"}, {\"id\": \"c\", \"text\": \"回收利用\"}, {\"id\": \"d\", \"text\": \"证明……正当；为……辩护\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (461,'recycle-1-context',1,154,'context','We ____ paper, glass and plastic at home.','[{\"id\": \"a\", \"text\": \"scatter\"}, {\"id\": \"b\", \"text\": \"recycle\"}, {\"id\": \"c\", \"text\": \"withdraw\"}, {\"id\": \"d\", \"text\": \"manipulate\"}]','{\"option_id\": \"b\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (462,'recycle-1-spelling',1,154,'spelling','回收利用（v.），首字母 r',NULL,'{\"accepted\": [\"recycle\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (463,'schedule-1-recognition',1,155,'recognition','schedule（n.）','[{\"id\": \"a\", \"text\": \"设施\"}, {\"id\": \"b\", \"text\": \"行程；旅行计划\"}, {\"id\": \"c\", \"text\": \"概念；观念\"}, {\"id\": \"d\", \"text\": \"日程；时间表\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (464,'schedule-1-context',1,155,'context','Let me check my ____ before I agree to the meeting.','[{\"id\": \"a\", \"text\": \"schedule\"}, {\"id\": \"b\", \"text\": \"controversy\"}, {\"id\": \"c\", \"text\": \"issue\"}, {\"id\": \"d\", \"text\": \"neighbourhood\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (465,'schedule-1-spelling',1,155,'spelling','日程；时间表（n.），首字母 s',NULL,'{\"accepted\": [\"schedule\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (466,'tuition-1-recognition',1,156,'recognition','tuition（n.）','[{\"id\": \"a\", \"text\": \"学费\"}, {\"id\": \"b\", \"text\": \"概念；观念\"}, {\"id\": \"c\", \"text\": \"证据\"}, {\"id\": \"d\", \"text\": \"截止日期\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (467,'tuition-1-context',1,156,'context','Many students take part-time jobs to pay their ____.','[{\"id\": \"a\", \"text\": \"deadline\"}, {\"id\": \"b\", \"text\": \"curriculum\"}, {\"id\": \"c\", \"text\": \"issue\"}, {\"id\": \"d\", \"text\": \"tuition\"}]','{\"option_id\": \"d\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (468,'tuition-1-spelling',1,156,'spelling','学费（n.），首字母 t',NULL,'{\"accepted\": [\"tuition\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (469,'volunteer-1-recognition',1,157,'recognition','volunteer（n.）','[{\"id\": \"a\", \"text\": \"志愿者\"}, {\"id\": \"b\", \"text\": \"课程（体系）\"}, {\"id\": \"c\", \"text\": \"使用权；接近的机会\"}, {\"id\": \"d\", \"text\": \"住处；住宿\"}]','{\"option_id\": \"a\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (470,'volunteer-1-context',1,157,'context','She works as a ____ at the local hospital.','[{\"id\": \"a\", \"text\": \"fair\"}, {\"id\": \"b\", \"text\": \"curriculum\"}, {\"id\": \"c\", \"text\": \"volunteer\"}, {\"id\": \"d\", \"text\": \"consequence\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (471,'volunteer-1-spelling',1,157,'spelling','志愿者（n.），首字母 v',NULL,'{\"accepted\": [\"volunteer\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (472,'organise-1-recognition',1,158,'recognition','organise（v.）','[{\"id\": \"a\", \"text\": \"毕业\"}, {\"id\": \"b\", \"text\": \"下降；减少\"}, {\"id\": \"c\", \"text\": \"组织；安排\"}, {\"id\": \"d\", \"text\": \"夸大；夸张\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (473,'organise-1-context',1,158,'context','The students will ____ a charity concert.','[{\"id\": \"a\", \"text\": \"justify\"}, {\"id\": \"b\", \"text\": \"emerge\"}, {\"id\": \"c\", \"text\": \"organise\"}, {\"id\": \"d\", \"text\": \"persist\"}]','{\"option_id\": \"c\"}','{\"type\": \"choice\"}','published');
INSERT INTO `questions` (`id`, `logical_key`, `version`, `sense_id`, `skill_type`, `prompt`, `options_json`, `answers_json`, `grading_policy_json`, `status`) VALUES (474,'organise-1-spelling',1,158,'spelling','组织；安排（v.），首字母 o',NULL,'{\"accepted\": [\"organise\", \"organize\"]}','{\"trim\": true, \"type\": \"text\", \"case_sensitive\": false}','published');
/*!40000 ALTER TABLE `questions` ENABLE KEYS */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
