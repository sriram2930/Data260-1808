"""
agents_demo.py — DATA-260 HW1, Part 2 (Agentic AI)

Two tiny agents (Planner, Reviewer) talk to each other through a local Ollama
model, followed by a deterministic Finalizer step, to turn a (title, content)
pair into exactly 3 topical tags + a <=25-word summary, printed as JSON.

Nothing in this file references a specific domain (courses, restaurants,
transit, etc.) — tags/summary are derived only from whatever title/content the
caller supplies, per the assignment's "do not hardcode your domain" rule.

Usage:
    python agents_demo.py --title "..." --content "..." --temperature 0.7
    python agents_demo.py --input-file cases/nondeterminism_input.json --temperature 0.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from langchain_ollama import ChatOllama

DEFAULT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_BASE_URL = "http://localhost:11434"


# --------------------------------------------------------------------------
# Structured output schemas — Ollama's JSON-schema-constrained generation
# (via langchain's with_structured_output) forces the model to emit JSON
# matching these shapes, so parsing failures should be rare.
# --------------------------------------------------------------------------

class PlannerOutput(BaseModel):
    tags: List[str] = Field(
        description="Exactly 3 short topical tags describing the given TITLE/CONTENT."
    )
    summary: str = Field(
        description="One sentence summarizing the given TITLE/CONTENT, at most 25 words."
    )


class ReviewerOutput(BaseModel):
    tags: List[str] = Field(description="Exactly 3 corrected/confirmed topical tags.")
    summary: str = Field(description="Corrected/confirmed one-sentence summary, at most 25 words.")
    approved: bool = Field(description="True if the Planner's draft needed no changes.")
    changes: str = Field(description="Short note on what was changed, or 'none'.")


PLANNER_SYSTEM_PROMPT = """You are the Planner in a two-agent content-tagging pipeline.
You will be given a TITLE and CONTENT. Read them carefully and produce:
1. Exactly 3 short topical tags (1-4 words each) that describe what the text is about.
2. A one-sentence summary of the text, at most 25 words.
Base the tags and summary strictly on the given TITLE and CONTENT only. Do not invent
facts that are not present in the text, and do not assume any particular subject domain
in advance — infer everything from the text itself."""

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer in a two-agent content-tagging pipeline.
You will be given the original TITLE and CONTENT, plus the Planner's draft tags and
summary. Check the draft against these rules:
1. There must be exactly 3 tags, each a short topical phrase genuinely relevant to the
   text (reject vague filler like "general" or "misc").
2. The summary must be a single sentence, at most 25 words, and faithful to the content
   (no invented facts, nothing not supported by the text).
If the draft already satisfies both rules, return it unchanged with approved=true and
changes="none". Otherwise, correct the tags and/or summary yourself and return the
corrected version with approved=false and a short note in changes describing what you
fixed."""


def _word_count(text: str) -> int:
    return len(text.split())


def _enforce_contract(tags: List[str], summary: str) -> tuple[List[str], str, List[str]]:
    """Deterministic Finalizer logic: guarantee exactly 3 tags and a <=25-word
    summary no matter what the model produced. Returns (tags, summary, notes)."""
    notes: List[str] = []

    # De-duplicate while preserving order, drop empty/whitespace-only tags.
    seen = set()
    clean_tags = []
    for t in tags:
        t = t.strip()
        if t and t.lower() not in seen:
            clean_tags.append(t)
            seen.add(t.lower())

    if len(clean_tags) > 3:
        notes.append(f"truncated {len(clean_tags)} tags down to 3")
        clean_tags = clean_tags[:3]
    elif len(clean_tags) < 3:
        notes.append(f"padded {len(clean_tags)} tag(s) up to 3 with 'unspecified'")
        while len(clean_tags) < 3:
            clean_tags.append("unspecified")

    words = summary.split()
    if len(words) > 25:
        notes.append(f"truncated summary from {len(words)} to 25 words")
        summary = " ".join(words[:25])

    return clean_tags, summary.strip(), notes


def run_pipeline(
    title: str,
    content: str,
    temperature: float = 0.7,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
) -> dict:
    """Run Planner -> Reviewer -> Finalizer once. Returns a dict with every
    intermediate step plus timing, so callers (CLI or the Part-3 batch
    runner) can both print a transcript and log raw metrics."""

    llm = ChatOllama(model=model, temperature=temperature, base_url=base_url)
    planner_llm = llm.with_structured_output(PlannerOutput)
    reviewer_llm = llm.with_structured_output(ReviewerOutput)

    user_block = f"TITLE: {title}\n\nCONTENT: {content}"

    t0 = time.perf_counter()

    planner_result: PlannerOutput = planner_llm.invoke(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ]
    )

    reviewer_user_block = (
        f"{user_block}\n\n"
        f"PLANNER DRAFT TAGS: {json.dumps(planner_result.tags)}\n"
        f"PLANNER DRAFT SUMMARY: {planner_result.summary}"
    )
    reviewer_result: ReviewerOutput = reviewer_llm.invoke(
        [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": reviewer_user_block},
        ]
    )

    latency_ms = (time.perf_counter() - t0) * 1000

    final_tags, final_summary, finalizer_notes = _enforce_contract(
        reviewer_result.tags, reviewer_result.summary
    )

    publish = {
        "tags": final_tags,
        "summary": final_summary,
        "model": model,
        "temperature": temperature,
        "reviewer_approved": reviewer_result.approved,
        "reviewer_changes": reviewer_result.changes,
        "finalizer_notes": finalizer_notes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "input": {"title": title, "content": content},
        "planner": planner_result.model_dump(),
        "reviewer": reviewer_result.model_dump(),
        "publish": publish,
        "latency_ms": latency_ms,
    }


def _print_transcript(result: dict) -> None:
    print("=== INPUT ===")
    print(json.dumps(result["input"], indent=2))
    print("\n=== PLANNER OUTPUT ===")
    print(json.dumps(result["planner"], indent=2))
    print("\n=== REVIEWER OUTPUT ===")
    print(json.dumps(result["reviewer"], indent=2))
    print("\n=== FINALIZED / PUBLISH OUTPUT ===")
    print(json.dumps(result["publish"], indent=2))
    print(f"\n(pipeline latency: {result['latency_ms']:.1f} ms)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Planner -> Reviewer -> Finalizer tagging demo")
    parser.add_argument("--title", help="Entity title/name")
    parser.add_argument("--content", help="Entity content/description")
    parser.add_argument("--input-file", help="JSON file with {\"title\": ..., \"content\": ...}")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        title, content = payload["title"], payload["content"]
    elif args.title and args.content:
        title, content = args.title, args.content
    else:
        parser.error("Provide either --input-file or both --title and --content")
        return

    result = run_pipeline(
        title=title,
        content=content,
        temperature=args.temperature,
        model=args.model,
        base_url=args.base_url,
    )
    _print_transcript(result)


if __name__ == "__main__":
    main()
