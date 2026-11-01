"""
Part-10/kafka_config.py -- DATA-260 HW8 (shared Kafka constants)

Single source of truth for the bootstrap server and the two PREFIX-prefixed
topics Part 1's request/response service uses, so worker.py, api.py, and
homework_demo.py can't accidentally drift out of sync with each other.
"""

from __future__ import annotations

import os

# localhost:9092 for scripts run on the host (homework_demo.py, test
# scripts); the worker/api containers override this via the
# BOOTSTRAP_SERVERS env var to reach the broker's internal Docker-network
# listener (s1808-kafka:29092) instead, since "localhost" inside a
# container means the container itself, not the Kafka container.
BOOTSTRAP_SERVERS = os.environ.get("BOOTSTRAP_SERVERS", "localhost:9092")

ENTITY_REQUESTS_TOPIC = "s1808_entity_requests"
ENTITY_RESPONSES_TOPIC = "s1808_entity_responses"

PORT_BASE = 8008
