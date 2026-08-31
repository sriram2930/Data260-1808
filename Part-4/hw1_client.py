"""
hw1_client.py — DATA-260 HW1, Part 4 (Model Client and Token Accounting)

Small command-line chat demo built on top of src/model_client.py. Loads AGENT.md
as the system prompt (a strict bullet-only code-review contract), then runs an
interactive REPL that:
  - prints input/output/total tokens after every model response,
  - supports a /stats command (turn count, cumulative tokens, serialized
    conversation-history length) that does NOT alter the history,
  - prints cumulative input tokens, output tokens, and turn count on exit.

Usage:
    python hw1_client.py
Type messages at the "> " prompt. Special commands: /stats, /exit (or /quit,
or Ctrl-D / EOF).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.model_client import ModelClient, DEFAULT_MODEL

HERE = Path(__file__).parent
AGENT_MD = HERE / "AGENT.md"


def load_system_prompt() -> str:
    return AGENT_MD.read_text(encoding="utf-8")


def print_turn_usage(turn: int, usage: dict) -> None:
    print(
        f"(turn {turn} tokens - input: {usage['input_tokens']}, "
        f"output: {usage['output_tokens']}, total: {usage['total_tokens']})"
    )


def print_stats(history: list[dict], turn: int, cum_input: int, cum_output: int) -> None:
    serialized_len = len(json.dumps(history))
    print("=== /stats ===")
    print(f"turn count: {turn}")
    print(f"cumulative input tokens: {cum_input}")
    print(f"cumulative output tokens: {cum_output}")
    print(f"cumulative total tokens: {cum_input + cum_output}")
    print(f"serialized conversation-history length: {serialized_len} chars")
    print("=== end /stats ===")


def main() -> None:
    client = ModelClient(model=DEFAULT_MODEL)
    history: list[dict] = [{"role": "system", "content": load_system_prompt()}]

    turn = 0
    cum_input = 0
    cum_output = 0

    print(f"hw1_client.py - model={DEFAULT_MODEL} - AGENT.md loaded as system prompt")
    print("Type a message, or /stats, or /exit (Ctrl-D also exits).\n")

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print()
            break

        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            break
        if user_input == "/stats":
            # Read-only: never appended to history, never counted as a turn.
            print_stats(history, turn, cum_input, cum_output)
            continue

        history.append({"role": "user", "content": user_input})
        result = client.complete(history)
        history.append({"role": "assistant", "content": result["content"]})

        turn += 1
        cum_input += result["usage"]["input_tokens"]
        cum_output += result["usage"]["output_tokens"]

        print(f"[assistant]: {result['content']}")
        print_turn_usage(turn, result["usage"])
        print()

    print("=== session ended ===")
    print(f"cumulative input tokens: {cum_input}")
    print(f"cumulative output tokens: {cum_output}")
    print(f"turn count: {turn}")


if __name__ == "__main__":
    main()
