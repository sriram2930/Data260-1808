"""
Part-15/tracing.py -- DATA-260 HW10, Part 4.1 (structured trace spans)

One request = one trace. trace_id IS the HW8 correlation_id (no second id is ever created).
Every pipeline stage appends one JSON span (one line) to reports/hw10/raw/spans.jsonl:

    {"trace_id", "stage", "start_time", "end_time", "start_ms", "end_ms", "duration_ms",
     "status": "ok" | "error", "error": str | null, "attrs": {...}}

Stages written by the system:
    cache_lookup                          client   embed + Redis KNN (attrs.cache_hit true/false)
    facts_lookup                          client   MySQL grounding facts (miss path only)
    queue_inbox / queue_tasks /
    queue_drafts / queue_final            Kafka    producer send time -> consumer starts work
    planner / writer / reviewer           agents   the model call (+ retries) for that stage
    request                               client   ingress -> answer returned (the user-visible latency)
    evaluation                            judge    plan/draft/final G-Eval run for the trace

Spans from several processes append to the same file; each span is one short line written with a
single O_APPEND write, which is atomic enough for this volume.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "reports" / "hw10" / "raw"
SPANS_PATH = Path(os.environ.get("HW10_SPANS_PATH", RAW_DIR / "spans.jsonl"))


def now_ms() -> float:
    """Wall-clock epoch milliseconds (comparable across processes and with Kafka record timestamps)."""
    return time.time() * 1000.0


def iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat(timespec="milliseconds")


def write_span(
    trace_id: Optional[str],
    stage: str,
    start_ms: float,
    end_ms: float,
    status: str = "ok",
    error: Optional[str] = None,
    **attrs,
) -> dict:
    span = {
        "trace_id": trace_id,
        "stage": stage,
        "start_time": iso(start_ms),
        "end_time": iso(end_ms),
        "start_ms": round(start_ms, 3),
        "end_ms": round(end_ms, 3),
        "duration_ms": round(end_ms - start_ms, 3),
        "status": status,
        "error": error,
        "attrs": attrs,
    }
    SPANS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(span, default=str) + "\n").encode("utf-8")
    fd = os.open(SPANS_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return span


@contextmanager
def span(trace_id: Optional[str], stage: str, **attrs) -> Iterator[dict]:
    """Time a block. Mutate the yielded dict to add attributes; an exception marks the span as error and re-raises."""
    extra: dict = dict(attrs)
    start = now_ms()
    try:
        yield extra
    except Exception as exc:  # noqa: BLE001 -- recorded, then re-raised
        write_span(trace_id, stage, start, now_ms(), "error", f"{type(exc).__name__}: {exc}", **extra)
        raise
    else:
        write_span(trace_id, stage, start, now_ms(), "ok", None, **extra)


def read_spans(path: Path = SPANS_PATH) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue  # a torn line must never break the dashboard
    return out


STAGE_ORDER = [
    "request", "cache_lookup", "facts_lookup", "queue_inbox", "planner", "queue_tasks", "writer",
    "queue_drafts", "reviewer", "queue_final", "evaluation",
]
