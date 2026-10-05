mysql: [Warning] Using a password on the command line interface can be insecure.
*************************** 1. row ***************************
       Table: courses
Create Table: CREATE TABLE `courses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `course_code` varchar(32) NOT NULL,
  `course_title` varchar(255) NOT NULL,
  `submitter_email` varchar(255) DEFAULT NULL,
  `description` text,
  `department` varchar(64) DEFAULT NULL,
  `agree_terms` tinyint(1) DEFAULT NULL,
  `department_id` int DEFAULT NULL,
  `seats_available` int NOT NULL DEFAULT '30',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `course_code` (`course_code`),
  KEY `ix_courses_course_code` (`course_code`),
  KEY `ix_courses_department` (`department`),
  KEY `fk_courses_department` (`department_id`),
  CONSTRAINT `fk_courses_department` FOREIGN KEY (`department_id`) REFERENCES `departments` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5005 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
*************************** 1. row ***************************
       Table: departments
Create Table: CREATE TABLE `departments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `building` varchar(128) DEFAULT NULL,
  `dept_code` varchar(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_departments_dept_code` (`dept_code`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
