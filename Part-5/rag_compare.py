"""
Part-5/rag_compare.py -- DATA-260 HW3, Part 2 (Compare Three LlamaIndex
Chunking Techniques, Retrieval-Only RAG)

Builds three separate in-memory vector indexes over the same local SJSU
domain corpus (reports/hw03/CORPUS_MANIFEST.json / Part-5/corpus/*.txt), one
per chunking technique:

  1. Token-based      -- TokenTextSplitter
  2. Semantic          -- SemanticSplitterNodeParser
  3. Sentence-window   -- SentenceWindowNodeParser

and a shared retrieval-only helper that, for a query and k, prints/returns
the query embedding (dimension + first 8 values), the top-k nodes with store
similarity score, an explicitly recomputed cosine similarity against the
query, chunk length, and a short preview -- plus the shapes of the query
vector and the stacked doc vectors.

This module only builds the pipelines and exposes retrieve(); the actual
experiment run (looping over questions.yaml, writing raw/ output) lives in
run_retrieval_comparison.py so this file can be imported and reused.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)
from llama_index.core.schema import TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "corpus"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Token chunking: 256 tokens with 40-token overlap keeps most FAQ Q&A pairs
# intact as one chunk (the corpus's paragraphs run roughly 60-150 words) while
# still splitting the handful of much longer pages.
TOKEN_CHUNK_SIZE = 256
TOKEN_CHUNK_OVERLAP = 40

# Semantic chunking: buffer_size=1 (compare each sentence to its immediate
# neighbor, the SemanticSplitterNodeParser default) using the same embed
# model as everything else.
SEMANTIC_BUFFER_SIZE = 1
SEMANTIC_BREAKPOINT_PERCENTILE = 95

# Sentence-window: 3 sentences of context on each side of the indexed
# sentence, stored in metadata for potential downstream generation (not used
# here since this is retrieval-only).
SENTENCE_WINDOW_SIZE = 3

TECHNIQUES = ["token", "semantic", "sentence_window"]


def load_corpus() -> list[Document]:
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        docs.append(Document(text=text, metadata={"file_name": path.name}))
    return docs


_embed_model = None


def get_embed_model() -> HuggingFaceEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
    return _embed_model


def build_nodes(technique: str, docs: list[Document]) -> list[TextNode]:
    embed_model = get_embed_model()
    if technique == "token":
        splitter = TokenTextSplitter(
            chunk_size=TOKEN_CHUNK_SIZE, chunk_overlap=TOKEN_CHUNK_OVERLAP
        )
        nodes = splitter.get_nodes_from_documents(docs)
    elif technique == "semantic":
        splitter = SemanticSplitterNodeParser(
            buffer_size=SEMANTIC_BUFFER_SIZE,
            breakpoint_percentile_threshold=SEMANTIC_BREAKPOINT_PERCENTILE,
            embed_model=embed_model,
        )
        nodes = splitter.get_nodes_from_documents(docs)
    elif technique == "sentence_window":
        splitter = SentenceWindowNodeParser.from_defaults(
            window_size=SENTENCE_WINDOW_SIZE,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )
        nodes = splitter.get_nodes_from_documents(docs)
    else:
        raise ValueError(f"unknown technique: {technique}")
    return nodes


def build_index(nodes: list[TextNode]) -> VectorStoreIndex:
    # No vector_store= kwarg -> LlamaIndex defaults to SimpleVectorStore, an
    # in-memory store, which is exactly what the assignment asks for.
    return VectorStoreIndex(nodes, embed_model=get_embed_model())


def build_all_pipelines() -> dict[str, dict[str, Any]]:
    """Returns {technique: {"nodes": [...], "index": VectorStoreIndex}}."""
    docs = load_corpus()
    pipelines = {}
    for tech in TECHNIQUES:
        nodes = build_nodes(tech, docs)
        index = build_index(nodes)
        pipelines[tech] = {"nodes": nodes, "index": index}
    return pipelines


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def retrieve(
    technique: str,
    index: VectorStoreIndex,
    query: str,
    k: int = 5,
    print_output: bool = True,
) -> dict[str, Any]:
    """Retrieval-only: embeds the query, retrieves top-k nodes, and for each
    computes store score, an explicitly recomputed cosine similarity, chunk
    length, and a preview. Returns a dict with everything needed for both the
    printed table and the raw/ JSONL row, including query/doc vector shapes."""
    embed_model = get_embed_model()

    t0 = time.perf_counter()
    query_vec = np.array(embed_model.get_query_embedding(query))
    retriever = index.as_retriever(similarity_top_k=k)
    results = retriever.retrieve(query)
    latency_ms = (time.perf_counter() - t0) * 1000

    doc_vecs = []
    rows = []
    for rank, r in enumerate(results, start=1):
        node = r.node
        store_score = r.score
        # Recompute the document embedding explicitly rather than trusting a
        # cached one, so the printed cosine similarity is independently
        # verifiable against the store score.
        doc_vec = np.array(embed_model.get_text_embedding(node.get_content()))
        doc_vecs.append(doc_vec)
        cos = cosine_sim(query_vec, doc_vec)
        text = node.get_content()
        rows.append({
            "rank": rank,
            "store_score": store_score,
            "cosine_sim": cos,
            "chunk_len": len(text),
            "preview": text[:160].replace("\n", " "),
            "source_file": node.metadata.get("file_name", "?"),
        })

    doc_vecs_arr = np.stack(doc_vecs) if doc_vecs else np.zeros((0, query_vec.shape[0]))

    if print_output:
        print(f"\n=== technique={technique} | query={query!r} | k={k} ===")
        print(f"query embedding dim: {query_vec.shape[0]}, first 8 values: "
              f"{np.round(query_vec[:8], 4).tolist()}")
        print(f"query vector shape: {query_vec.shape}, stacked doc vectors shape: {doc_vecs_arr.shape}")
        print(f"{'rank':<5}{'store_score':<13}{'cosine_sim':<12}{'chunk_len':<11}preview")
        for row in rows:
            print(f"{row['rank']:<5}{row['store_score']:<13.4f}{row['cosine_sim']:<12.4f}"
                  f"{row['chunk_len']:<11}{row['preview']}")

    return {
        "technique": technique,
        "query": query,
        "k": k,
        "query_embedding_dim": int(query_vec.shape[0]),
        "query_embedding_first8": np.round(query_vec[:8], 6).tolist(),
        "query_vector_shape": list(query_vec.shape),
        "doc_vectors_shape": list(doc_vecs_arr.shape),
        "retrieval_latency_ms": latency_ms,
        "rows": rows,
    }


def chunk_stats(nodes: list[TextNode]) -> dict[str, float]:
    lengths = [len(n.get_content()) for n in nodes]
    return {
        "num_chunks": len(nodes),
        "avg_chunk_length_chars": sum(lengths) / len(lengths) if lengths else 0.0,
    }
