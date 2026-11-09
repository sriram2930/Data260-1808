"""
Part-13/semantic_cache.py -- DATA-260 HW9, Parts 2-3 (semantic response cache)

Sits at the ingress of the course Q&A endpoint, in front of the HW8
Planner -> Writer -> Reviewer pipeline (Part-11, over Kafka).

  hit  : nearest cached query has cosine similarity >= threshold
         -> return the stored final answer, pipeline NOT run (is_cached=True)
  miss : build grounding facts from s1808_rel, run the real HW8 pipeline via
         Kafka, store {query, embedding, answer, data_version}, return
         (is_cached=False)

Embeddings: sentence-transformers/all-MiniLM-L6-v2 (384-d, L2-normalised).
Storage:    Redis hashes under  s1808:semcache:<n>  with a RediSearch FLAT
            vector index (COSINE) named  s1808:idx:semcache.
Every Redis key starts with PREFIX (s1808).

Invalidation (Part 3.5): each entry stores `data_version`, a hash of the
s1808_rel rows its answer was built from. With validate_versions=True a hit
is only served if those rows still hash to the stored version; otherwise the
entry is evicted and the request is treated as a miss.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "Part-11"))

from domain_facts import facts_for  # noqa: E402

PREFIX = "s1808"
INDEX_NAME = f"{PREFIX}:idx:semcache"
KEY_PREFIX = f"{PREFIX}:semcache:"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
DEFAULT_THRESHOLD = 0.85

log = logging.getLogger("semantic_cache")


def now_ms() -> float:
    return time.perf_counter() * 1000.0


# --------------------------------------------------------------------------
# HW8 pipeline client: question -> s1808_inbox ... s1808_final (Kafka)
# --------------------------------------------------------------------------
class KafkaPipeline:
    """Sends one question through the HW8 agents and waits for the final answer."""

    def __init__(self, timeout_s: float = 300.0):
        from kafka_config import FINAL_TOPIC, INBOX_TOPIC
        from kafka_utils import make_consumer, make_producer

        self.inbox, self.final, self.timeout_s = INBOX_TOPIC, FINAL_TOPIC, timeout_s
        self.producer = make_producer()
        self.consumer = make_consumer(self.final, f"s1808_cache_{uuid.uuid4().hex}", auto_offset_reset="latest")

    def build_prompt(self, question: str, facts: list[str]) -> str:
        if facts:
            return (
                f"{question}\n\nCourse catalogue facts (answer using ONLY these facts):\n"
                + "\n".join(f"- {f}" for f in facts)
            )
        return (
            f"{question}\n\nNo course-catalogue facts match this question. If it is not about the university "
            "course catalogue, say you can only answer questions about the course catalogue."
        )

    def ask(self, question: str, facts: list[str]) -> str:
        cid = str(uuid.uuid4())
        self.producer.send(self.inbox, value={"correlation_id": cid, "question": self.build_prompt(question, facts)})
        self.producer.flush()
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            for records in self.consumer.poll(timeout_ms=500).values():
                for rec in records:
                    if rec.value.get("correlation_id") == cid:
                        return rec.value["answer"]
        raise TimeoutError("HW8 pipeline produced no final answer")

    def close(self) -> None:
        self.consumer.close()
        self.producer.close()


# --------------------------------------------------------------------------
class SemanticCache:
    def __init__(
        self,
        agent: Callable[[str, list[str]], str],
        threshold: float = DEFAULT_THRESHOLD,
        validate_versions: bool = False,
        redis_client: Optional[redis.Redis] = None,
    ):
        self.r = redis_client or redis.Redis(host="localhost", port=6379)  # bytes: embeddings are binary
        self.agent = agent
        self.threshold = threshold
        self.validate_versions = validate_versions
        self._model = None
        self.ensure_index()

    # ---- embeddings ------------------------------------------------------
    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBED_MODEL)
        return self._model

    def embed(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True).astype(np.float32)

    # ---- index / storage -------------------------------------------------
    def ensure_index(self) -> None:
        try:
            self.r.ft(INDEX_NAME).info()
        except redis.ResponseError:
            self.r.ft(INDEX_NAME).create_index(
                [
                    TextField("query"),
                    VectorField("embedding", "FLAT", {"TYPE": "FLOAT32", "DIM": DIM, "DISTANCE_METRIC": "COSINE"}),
                ],
                definition=IndexDefinition(prefix=[KEY_PREFIX], index_type=IndexType.HASH),
            )

    def flush(self) -> int:
        keys = list(self.r.scan_iter(match=f"{KEY_PREFIX}*"))
        if keys:
            self.r.delete(*keys)
        return len(keys)

    def store(self, query: str, vec: np.ndarray, answer: str, data_version: str) -> str:
        key = f"{KEY_PREFIX}{uuid.uuid4().hex[:12]}"
        self.r.hset(
            key,
            mapping={
                "query": query,
                "embedding": vec.tobytes(),
                "answer": answer,
                "data_version": data_version,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )
        return key

    def nearest(self, vec: np.ndarray) -> Optional[dict]:
        q = (
            Query("*=>[KNN 1 @embedding $vec AS dist]")
            .sort_by("dist")
            .return_fields("query", "answer", "data_version", "dist")
            .dialect(2)
        )
        res = self.r.ft(INDEX_NAME).search(q, query_params={"vec": vec.tobytes()})
        if not res.docs:
            return None
        d = res.docs[0]
        return {
            "key": d.id,
            "query": d.query,
            "answer": d.answer,
            "data_version": d.data_version,
            "similarity": 1.0 - float(d.dist),  # RediSearch COSINE returns distance = 1 - cos
        }

    # ---- request handler -------------------------------------------------
    def handle(self, question: str, store_on_miss: bool = True) -> dict:
        t0 = now_ms()
        vec = self.embed(question)
        t_embed = now_ms()
        hit = self.nearest(vec)
        t_search = now_ms()

        stale_evicted = None
        if hit and hit["similarity"] >= self.threshold:
            if self.validate_versions:
                current = facts_for(hit["query"])["version"]  # re-hash the rows the cached answer came from
                if current != hit["data_version"]:
                    stale_evicted = {"cached_query": hit["query"], "stored_version": hit["data_version"], "current_version": current}
                    self.r.delete(hit["key"])
                    log.info("CACHE STALE  query=%r matched=%r sim=%.3f stored_ver=%s current_ver=%s -> evicted",
                             question, hit["query"], hit["similarity"], hit["data_version"], current)
                    hit = None  # fall through to the miss path
            if hit:
                t1 = now_ms()
                log.info("CACHE HIT   sim=%.3f query=%r matched=%r", hit["similarity"], question, hit["query"])
                return {
                    "question": question, "answer": hit["answer"], "is_cached": True,
                    "similarity": round(hit["similarity"], 4), "matched_query": hit["query"],
                    "latency_ms": round(t1 - t0, 1),
                    "embed_ms": round(t_embed - t0, 1), "search_ms": round(t_search - t_embed, 1),
                    "agent_ms": 0.0, "stale_evicted": None,
                }

        # ---- miss path: facts -> real HW8 pipeline -> store -----------------
        best_sim = hit["similarity"] if hit else None
        t_pre = now_ms()
        f = facts_for(question)
        t_facts = now_ms()
        answer = self.agent(question, f["facts"])
        t_agent = now_ms()
        if store_on_miss:
            self.store(question, vec, answer, f["version"])
        t1 = now_ms()
        log.info("CACHE MISS  best_sim=%s query=%r (agent %.0f ms)",
                 f"{best_sim:.3f}" if best_sim is not None else "n/a", question, t_agent - t_facts)
        return {
            "question": question, "answer": answer, "is_cached": False,
            "similarity": round(best_sim, 4) if best_sim is not None else None,
            "matched_query": None, "latency_ms": round(t1 - t0, 1),
            "embed_ms": round(t_embed - t0, 1), "search_ms": round(t_search - t_embed, 1),
            "agent_ms": round(t_agent - t_facts, 1), "facts_ms": round(t_facts - t_pre, 1),
            "stale_evicted": stale_evicted, "data_version": f["version"],
        }


def make_cache_with_kafka(threshold: float = DEFAULT_THRESHOLD, validate_versions: bool = False):
    pipeline = KafkaPipeline()
    return SemanticCache(pipeline.ask, threshold, validate_versions), pipeline


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, default=str)
