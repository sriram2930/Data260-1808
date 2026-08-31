"""
src/model_client.py — DATA-260 HW1, Part 4 (Model Client and Token Accounting)

Reusable model-adapter module. Every model call made anywhere in this homework
goes through ModelClient.complete(messages, tools=None) — a stable interface
that would let the underlying model (or provider) be swapped later without
touching any calling code.

Uses the `ollama` Python client directly (rather than the langchain wrapper used
in agents_demo.py) because Ollama's raw chat response carries exact token counts
(`prompt_eval_count` / `eval_count`) needed for the per-turn accounting this part
requires.
"""

from __future__ import annotations

from typing import Any, Optional

import ollama

DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_HOST = "http://localhost:11434"


class ModelClient:
    """Thin, stable adapter around a local Ollama model."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST):
        self.model = model
        self._client = ollama.Client(host=host)

    def complete(self, messages: list[dict], tools: Optional[list] = None) -> dict:
        """Send `messages` (OpenAI-style role/content dicts) to the model and
        return a normalized dict: content, role, tool_calls, usage (input/
        output/total token counts for this turn only), and the raw provider
        response for anything caller-specific that isn't normalized here."""
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat(**kwargs)
        message = response["message"]

        input_tokens = response.get("prompt_eval_count", 0)
        output_tokens = response.get("eval_count", 0)

        return {
            "content": message.get("content", ""),
            "role": message.get("role", "assistant"),
            "tool_calls": message.get("tool_calls"),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "raw": response,
        }
