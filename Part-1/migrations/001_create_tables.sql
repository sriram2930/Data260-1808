-- DATA-260 HW4 Part 3.1 -- schema used to create the seeded rows
-- Dumped via SHOW CREATE TABLE from the live s1808_rel database
-- (tables themselves are created by db.py/models.py + Base.metadata.create_all(),
-- this file documents the resulting schema, as the assignment asks for)

CREATE TABLE `courses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `course_code` varchar(32) NOT NULL,
  `course_title` varchar(255) NOT NULL,
  `submitter_email` varchar(255) DEFAULT NULL,
  `description` text,
  `department` varchar(64) DEFAULT NULL,
  `agree_terms` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_courses_course_code` (`course_code`)
) ENGINE=InnoDB AUTO_INCREMENT=5003 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `sections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `course_id` int NOT NULL,
  `semester` varchar(32) NOT NULL,
  `instructor` varchar(128) NOT NULL,
  `enrolled_count` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_sections_course_id` (`course_id`),
  CONSTRAINT `sections_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=201 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `sessions` (
  `id` varchar(64) NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

