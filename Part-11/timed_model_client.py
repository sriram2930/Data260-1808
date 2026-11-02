"""
Part-11/timed_model_client.py -- DATA-260 HW8 (ModelClient with a real request timeout)

A local subclass of the shared HW1 ModelClient (Part-4/src/model_client.py)
that only adds one thing: a hard request timeout on the underlying Ollama
client. The shared adapter is intentionally left untouched (every other
homework in this repo uses it as-is) -- this exists only because HW8's
long-running consumer agents (planner/writer/reviewer) can otherwise hang
forever on a stuck Ollama request with zero CPU activity and no error,
something this exact Part 3.II test hit repeatedly in practice: Ollama's
/api/tags kept responding, but a specific /api/chat call never returned
and never showed up as active work in the model process. See AI_USE.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

import ollama  # noqa: E402
from src.model_client import DEFAULT_HOST, DEFAULT_MODEL, ModelClient  # noqa: E402

REQUEST_TIMEOUT_S = 120.0


class TimedModelClient(ModelClient):
    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST, temperature=None):
        self.model = model
        self.temperature = temperature
        self._client = ollama.Client(host=host, timeout=REQUEST_TIMEOUT_S)
