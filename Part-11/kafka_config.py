"""
Part-11/kafka_config.py -- DATA-260 HW8, Part 2 (shared Kafka constants)

Single source of truth for the bootstrap server and the four
PREFIX-prefixed topics the three-agent pipeline uses.
"""

from __future__ import annotations

import os

BOOTSTRAP_SERVERS = os.environ.get("BOOTSTRAP_SERVERS", "localhost:9092")

INBOX_TOPIC = "s1808_inbox"
TASKS_TOPIC = "s1808_tasks"
DRAFTS_TOPIC = "s1808_drafts"
FINAL_TOPIC = "s1808_final"
