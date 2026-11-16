"""
Part-15/qa_service.py -- DATA-260 HW10, Parts 2.1 and 4.1 (traced Q&A request path)

The HW9 ingress: semantic cache in front of the HW8 Planner -> Writer -> Reviewer pipeline, now with

  * trace_id == the HW8 correlation_id, from cache lookup through inbox/tasks/drafts/final;
  * one structured span per stage (Part-15/tracing.py);
  * a MessageCollector that consumes s1808_tasks / s1808_drafts / s1808_final / s1808_dead_letter
    and saves every raw message (content + topic/partition/offset/timestamps) to
    reports/hw10/raw/messages.jsonl, so the evaluator can join plan + draft + final by correlation_id.

Every wait is bounded: a stuck agent or a dead-lettered message ends the request with status "error".
Run the three HW8 agents first (Part-11/planner.py, writer.py, reviewer.py).
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for sub in ("Part-15", "Part-13", "Part-11"):
    sys.path.insert(0, str(REPO_ROOT / sub))

from kafka import KafkaConsumer  # noqa: E402
from kafka_config import BOOTSTRAP_SERVERS, DRAFTS_TOPIC, FINAL_TOPIC, INBOX_TOPIC, TASKS_TOPIC  # noqa: E402
from kafka_utils import DEAD_LETTER_TOPIC, make_producer, wait_for_assignment  # noqa: E402
from tracing import RAW_DIR, now_ms, span, write_span  # noqa: E402

MESSAGES_PATH = RAW_DIR / "messages.jsonl"
REQUESTS_PATH = RAW_DIR / "requests.jsonl"  # one line per request: the "own log" the dashboard summary reads
STAGE_OF_TOPIC = {INBOX_TOPIC: "planner", TASKS_TOPIC: "writer", DRAFTS_TOPIC: "reviewer"}


def log_request(rec: dict) -> None:
    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REQUESTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"logged_at_ms": round(now_ms(), 3), **rec}, default=str) + "\n")


class MessageCollector:
    """Consumes the pipeline's topics and keeps every message, keyed by correlation_id."""

    TOPICS = [TASKS_TOPIC, DRAFTS_TOPIC, FINAL_TOPIC, DEAD_LETTER_TOPIC]

    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            *self.TOPICS,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=f"s1808_hw10_collector_{uuid.uuid4().hex}",
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        wait_for_assignment(self.consumer)
        self.by_cid: dict[str, dict[str, dict]] = {}
        MESSAGES_PATH.parent.mkdir(parents=True, exist_ok=True)

    def poll(self, timeout_ms: int = 300) -> None:
        batches = self.consumer.poll(timeout_ms=timeout_ms)
        received = now_ms()  # taken AFTER the (blocking) poll returns, so queue_final is not understated/negative
        for records in batches.values():
            for rec in records:
                val = rec.value if isinstance(rec.value, dict) else {"raw": rec.value}
                cid = val.get("correlation_id")
                row = {
                    "correlation_id": cid, "topic": rec.topic, "partition": rec.partition, "offset": rec.offset,
                    "kafka_timestamp_ms": rec.timestamp, "received_ms": round(received, 3), "value": val,
                }
                with MESSAGES_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                if cid:
                    self.by_cid.setdefault(cid, {})[rec.topic] = row

    def close(self) -> None:
        self.consumer.close()


class TracedQA:
    def __init__(self, threshold: float = 0.90, validate_versions: bool = True, timeout_s: float = 240.0):
        from domain_facts import facts_for
        from semantic_cache import SemanticCache

        self.facts_for = facts_for
        self.cache = SemanticCache(agent=lambda q, f: "", threshold=threshold, validate_versions=validate_versions)
        self.producer = make_producer()
        self.collector = MessageCollector()
        self.timeout_s = timeout_s
        self.cache.embed("warm-up")  # load the embedding model once, outside any measured span

    # ------------------------------------------------------------------ helpers
    def _prompt(self, question: str, facts: list[str]) -> str:
        if facts:
            return (f"{question}\n\nCourse catalogue facts (answer using ONLY these facts):\n"
                    + "\n".join(f"- {f}" for f in facts))
        return (f"{question}\n\nNo course-catalogue facts match this question. If it is not about the university "
                "course catalogue, say you can only answer questions about the course catalogue.")

    def _wait(self, trace_id: str) -> tuple[Optional[dict], Optional[dict], Optional[str]]:
        """Bounded wait for the final message or a dead-letter record. Returns (final_row, dead_row, error)."""
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            self.collector.poll(300)
            got = self.collector.by_cid.get(trace_id, {})
            if FINAL_TOPIC in got:
                return got[FINAL_TOPIC], None, None
            if DEAD_LETTER_TOPIC in got:
                return None, got[DEAD_LETTER_TOPIC], None
        return None, None, f"TimeoutError: no final or dead-letter message within {self.timeout_s:.0f}s"

    # ------------------------------------------------------------------ main entry
    def ask(self, question: str, trace_id: Optional[str] = None, store_on_miss: bool = True) -> dict:
        trace_id = trace_id or str(uuid.uuid4())
        t0 = now_ms()
        out = {"trace_id": trace_id, "question": question, "is_cached": False, "similarity": None, "answer": None,
               "status": "ok", "error": None, "failed_stage": None}

        # ---- cache lookup span (hit and miss paths are distinguished by attrs.cache_hit)
        with span(trace_id, "cache_lookup") as a:
            vec = self.cache.embed(question)
            hit = self.cache.nearest(vec)
            sim = hit["similarity"] if hit else None
            served = bool(hit and sim >= self.cache.threshold)
            if served and self.cache.validate_versions:
                current = self.facts_for(hit["query"])["version"]
                if current != hit["data_version"]:
                    self.cache.r.delete(hit["key"])
                    served, a["stale_evicted"] = False, True
            a.update(cache_hit=served, similarity=None if sim is None else round(sim, 4),
                     threshold=self.cache.threshold,
                     matched_query=hit["query"] if served else None)
        out["similarity"] = None if sim is None else round(sim, 4)

        if served:
            out.update(is_cached=True, answer=hit["answer"])
            write_span(trace_id, "request", t0, now_ms(), "ok", None, path="cache_hit")
            out["latency_ms"] = round(now_ms() - t0, 1)
            log_request({"trace_id": trace_id, "question": question, "path": "cache_hit", "status": "ok", "error": None,
                         "similarity": out["similarity"], "latency_ms": out["latency_ms"], "start_ms": t0})
            return out

        # ---- miss path: grounding facts, then the real Kafka pipeline
        with span(trace_id, "facts_lookup"):
            f = self.facts_for(question)
        self.producer.send(INBOX_TOPIC, value={"correlation_id": trace_id, "question": self._prompt(question, f["facts"])})
        self.producer.flush()
        final_row, dead_row, err = self._wait(trace_id)

        if final_row is not None:
            tf = float(final_row["kafka_timestamp_ms"])
            write_span(trace_id, "queue_final", tf, float(final_row["received_ms"]), topic=FINAL_TOPIC,
                       partition=final_row["partition"], offset=final_row["offset"])
            out["answer"] = final_row["value"].get("answer")
            got = self.collector.by_cid.get(trace_id, {})
            out["facts"] = f["facts"]
            out["plan"] = got.get(TASKS_TOPIC, {}).get("value", {}).get("plan")
            out["draft"] = got.get(DRAFTS_TOPIC, {}).get("value", {}).get("draft")
            if store_on_miss and out["answer"]:
                self.cache.store(question, vec, out["answer"], f["version"])
        else:
            out["status"] = "error"
            if dead_row is not None:
                v = dead_row["value"]
                out["failed_stage"] = STAGE_OF_TOPIC.get(v.get("original_topic"), "unknown")
                out["error"] = f"{out['failed_stage']} failed after {v.get('retries')} retries: {v.get('error')}"
            else:
                out["error"] = err
        write_span(trace_id, "request", t0, now_ms(), out["status"], out["error"], path="cache_miss",
                   failed_stage=out["failed_stage"])
        out["latency_ms"] = round(now_ms() - t0, 1)
        log_request({"trace_id": trace_id, "question": question, "path": "cache_miss", "status": out["status"],
                     "error": out["error"], "failed_stage": out["failed_stage"], "similarity": out["similarity"],
                     "latency_ms": out["latency_ms"], "start_ms": t0, "facts": out.get("facts")})
        return out

    def ask_malformed(self, trace_id: Optional[str] = None) -> dict:
        """Failure demo: a message with no 'question' field. The Planner raises KeyError on every retry and the
        message is dead-lettered; the span log shows the planner span with status=error."""
        trace_id = trace_id or str(uuid.uuid4())
        t0 = now_ms()
        self.producer.send(INBOX_TOPIC, value={"correlation_id": trace_id})
        self.producer.flush()
        final_row, dead_row, err = self._wait(trace_id)
        stage = STAGE_OF_TOPIC.get(dead_row["value"].get("original_topic"), "unknown") if dead_row else None
        error = (f"{stage} failed after {dead_row['value'].get('retries')} retries: {dead_row['value'].get('error')}"
                 if dead_row else err or "unexpected success")
        write_span(trace_id, "request", t0, now_ms(), "error", error, path="malformed_input", failed_stage=stage)
        res = {"trace_id": trace_id, "status": "error", "failed_stage": stage, "error": error,
               "latency_ms": round(now_ms() - t0, 1)}
        log_request({**res, "question": None, "path": "malformed_input", "start_ms": t0})
        return res

    def close(self) -> None:
        self.collector.close()
        self.producer.close()
