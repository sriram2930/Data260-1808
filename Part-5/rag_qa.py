"""
Part-5/rag_qa.py -- DATA-260 HW4, Part 4 (Grounded RAG Question-Answering)

Builds one chunked, embedded index over the same domain corpus used in HW3
(Part-5/corpus/*.txt, 32 real SJSU pages -- well over the "at least 5
documents" minimum), then exposes three ways of answering a question so the
same question can be run through all three and compared:

  A) answer_no_rag       -- straight to the LLM, no retrieval at all.
  B) answer_basic_rag    -- top-k raw chunks dumped into the prompt as-is.
  C) answer_context_rag  -- top-k chunks with irrelevant/duplicate chunks
                             dropped, survivors labeled and ordered by
                             source, plus explicit grounding rules (answer
                             only from context, cite the source number,
                             refuse verbatim when the evidence is thin).

Generation goes through Part-4/src/model_client.py's ModelClient, same
adapter used everywhere else in this repo, rather than calling Ollama
directly here.
"""

from __future__ import annotations

import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
CORPUS_DIR = HERE / "corpus"

sys.path.insert(0, str(REPO_ROOT / "Part-4"))
from src.model_client import ModelClient, DEFAULT_MODEL  # noqa: E402

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

RELEVANCE_THRESHOLD = 0.30   # drop retrieved chunks scoring below this
DUPLICATE_THRESHOLD = 0.60   # word-overlap ratio above which two chunks count as near-duplicates

REFUSAL_TEXT = "I cannot answer this question from the provided documents"

_embed_model = None
_model_client = None
_index = None


def get_embed_model() -> HuggingFaceEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
    return _embed_model


def get_model_client() -> ModelClient:
    global _model_client
    if _model_client is None:
        _model_client = ModelClient(model=DEFAULT_MODEL)
    return _model_client


def build_index() -> VectorStoreIndex:
    global _index
    if _index is not None:
        return _index

    docs = [
        Document(text=p.read_text(encoding="utf-8"), metadata={"file_name": p.name})
        for p in sorted(CORPUS_DIR.glob("*.txt"))
    ]
    splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(docs)
    for i, node in enumerate(nodes):
        node.metadata["chunk_id"] = f"chunk-{i:04d}"

    _index = VectorStoreIndex(nodes, embed_model=get_embed_model())
    return _index


def retrieve_chunks(query: str, k: int = 3, print_output: bool = True) -> list[dict[str, Any]]:
    """Retrieve top-k chunks and print them with source + score BEFORE any
    LLM call, so a retrieval problem is visible separately from a generation
    problem, per the assignment."""
    index = build_index()
    retriever = index.as_retriever(similarity_top_k=k)
    results = retriever.retrieve(query)

    chunks = [
        {
            "chunk_id": r.node.metadata.get("chunk_id", "?"),
            "source": r.node.metadata.get("file_name", "?"),
            "score": r.score,
            "text": r.node.get_content(),
        }
        for r in results
    ]

    if print_output:
        print(f"--- retrieved chunks for {query!r} (k={k}) ---")
        for c in chunks:
            preview = c["text"][:120].replace("\n", " ")
            print(f"  [{c['chunk_id']}] source={c['source']} score={c['score']:.4f} :: {preview}")

    return chunks


def _word_set(text: str) -> set[str]:
    return set(text.lower().split())


def curate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The context-engineering step: drop chunks scoring below
    RELEVANCE_THRESHOLD, then drop near-duplicates (kept: the
    higher-scoring one of any pair whose word overlap exceeds
    DUPLICATE_THRESHOLD), then sort survivors by score descending."""
    relevant = [c for c in chunks if c["score"] >= RELEVANCE_THRESHOLD]
    relevant.sort(key=lambda c: c["score"], reverse=True)

    kept: list[dict[str, Any]] = []
    for c in relevant:
        is_dup = False
        for k in kept:
            ratio = SequenceMatcher(None, c["text"], k["text"]).ratio()
            words_a, words_b = _word_set(c["text"]), _word_set(k["text"])
            jaccard = len(words_a & words_b) / max(1, len(words_a | words_b))
            if ratio >= DUPLICATE_THRESHOLD or jaccard >= DUPLICATE_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            kept.append(c)
    return kept


def call_llm(messages: list[dict]) -> dict:
    t0 = time.perf_counter()
    result = get_model_client().complete(messages)
    latency_ms = (time.perf_counter() - t0) * 1000
    return {"content": result["content"], "usage": result["usage"], "latency_ms": latency_ms}


def answer_no_rag(question: str) -> dict:
    messages = [
        {"role": "system", "content": "Answer the user's question directly and concisely."},
        {"role": "user", "content": question},
    ]
    result = call_llm(messages)
    return {"config": "no_rag", "question": question, "chunks_used": [], **result}


def answer_basic_rag(question: str, k: int = 3) -> dict:
    chunks = retrieve_chunks(question, k=k)
    context = "\n\n".join(c["text"] for c in chunks)
    messages = [
        {"role": "system", "content": "Use the following context to answer the question."},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]
    result = call_llm(messages)
    return {"config": "basic_rag", "question": question, "chunks_used": chunks, **result}


CONTEXT_RAG_SYSTEM_PROMPT = f"""You are a grounded question-answering assistant.
You must answer ONLY using the numbered SOURCE excerpts provided below -- do not
use any outside knowledge. For every factual claim, cite the source number in
square brackets, e.g. [1]. If the sources do not contain enough information to
answer confidently, respond with EXACTLY this sentence and nothing else:
"{REFUSAL_TEXT}\""""


def answer_context_rag(question: str, k: int = 3) -> dict:
    raw_chunks = retrieve_chunks(question, k=k)
    curated = curate_chunks(raw_chunks)

    if not curated:
        labeled_context = "(no sufficiently relevant sources were retrieved)"
    else:
        labeled_context = "\n\n".join(
            f"SOURCE [{i+1}] (file: {c['source']}):\n{c['text']}" for i, c in enumerate(curated)
        )

    messages = [
        {"role": "system", "content": CONTEXT_RAG_SYSTEM_PROMPT},
        {"role": "user", "content": f"{labeled_context}\n\nQUESTION: {question}"},
    ]
    result = call_llm(messages)
    return {"config": "context_rag", "question": question, "chunks_used": curated, **result}
