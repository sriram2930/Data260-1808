"""
Part-4/file_memory.py -- DATA-260 HW6, Part 4 (file-based memory + consolidation)

A second, independent memory system alongside Part 2's MongoDB-backed one:
AGENT.md (durable project/agent instructions) and MEMORY.md (durable facts
learned from conversations), both loaded into the system prompt as plain
text. No database involved -- everything here is two Markdown files on
disk, which is the whole point of comparing it against MongoDB memory in
the report.

Consolidation trigger (both must be checked, either is sufficient):
  - MEMORY.md has more than 40 non-empty, non-comment lines, or
  - its recorded consolidation time (the `<!-- last_consolidated: ... -->`
    comment on line 1) is more than 24 hours old

Consolidation itself goes through the local Ollama model (same ModelClient
adapter as everything else in this repo): merge duplicate facts, resolve
contradictions explicitly (write down which version won and why, never
just silently drop one side), and leave a date on the new content.
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent
AGENT_PATH = HERE / "AGENT.md"
MEMORY_PATH = HERE / "MEMORY.md"

MAX_MEMORY_LINES = 40
MAX_MEMORY_AGE_HOURS = 24

REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "Part-1"))
from src.model_client import ModelClient  # noqa: E402

_model_client: Optional[ModelClient] = None
_embed_model = None


def get_model_client() -> ModelClient:
    global _model_client
    if _model_client is None:
        _model_client = ModelClient()
    return _model_client


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        _embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def load_agent_md() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def load_memory_md(path: Path = MEMORY_PATH) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_system_prompt_prefix() -> str:
    """What gets prepended to the system prompt: both files' full content,
    clearly labeled so the model (and a human reading a logged prompt) can
    tell which is durable project instruction vs. a learned fact."""
    return (
        "=== AGENT.md (durable project/agent instructions) ===\n"
        f"{load_agent_md()}\n\n"
        "=== MEMORY.md (durable facts from previous conversations) ===\n"
        f"{load_memory_md()}"
    )


def parse_last_consolidated(text: str) -> Optional[datetime.datetime]:
    m = re.search(r"<!--\s*last_consolidated:\s*([0-9T:\-]+)\s*-->", text)
    if not m:
        return None
    try:
        return datetime.datetime.fromisoformat(m.group(1))
    except ValueError:
        return None


def non_empty_non_comment_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") or stripped.startswith("#"):
            continue
        out.append(line)
    return out


def needs_consolidation(path: Path = MEMORY_PATH) -> tuple[bool, str]:
    text = load_memory_md(path)
    lines = non_empty_non_comment_lines(text)
    if len(lines) > MAX_MEMORY_LINES:
        return True, f"{len(lines)} non-empty/non-comment lines (> {MAX_MEMORY_LINES})"
    last = parse_last_consolidated(text)
    if last is None:
        return True, "no last_consolidated timestamp found"
    age_hours = (datetime.datetime.utcnow() - last).total_seconds() / 3600
    if age_hours > MAX_MEMORY_AGE_HOURS:
        return True, f"last consolidated {age_hours:.1f}h ago (> {MAX_MEMORY_AGE_HOURS}h)"
    return False, f"{len(lines)} lines, last consolidated {age_hours:.1f}h ago"


def _bullet_text(line: str) -> str:
    return line.lstrip("- ").strip()


RESOLVE_CONTRADICTION_PROMPT = """These two facts about the same project contradict each other:
1: {a}
2: {b}

Reply with ONE line that states which is now considered current and
explicitly names the old value it replaced, so no information is silently
lost (e.g. "X is now 20, previously stated as 12; 20 is current"). If you
cannot tell which is correct from the two lines alone, say so explicitly
instead of guessing (e.g. "X was stated as both 12 and 20; which is correct
is unresolved and needs a human to confirm"). Reply with ONLY that one
line, no extra commentary."""

_POLARITY_PAIRS = [
    ("always", "blocked"), ("always", "never"), ("allowed", "blocked"),
    ("allowed", "denied"), ("enabled", "disabled"), ("true", "false"),
]


def _has_polarity_conflict(a: str, b: str) -> bool:
    a_low, b_low = a.lower(), b.lower()
    for w1, w2 in _POLARITY_PAIRS:
        if (w1 in a_low and w2 in b_low) or (w2 in a_low and w1 in b_low):
            return True
    return False


def _find_related_pairs(lines: list[str], threshold: float = 0.68) -> list[tuple[int, int, float]]:
    """Embedding cosine similarity finds pairs that are 'about the same
    thing' (whether duplicate or contradiction, both score high since both
    share almost all their words). Classifying WHICH of the two a given pair
    is happens afterward with a deterministic check, not the embedding
    itself -- see _classify_pair."""
    import numpy as np

    embed_model = get_embed_model()
    texts = [_bullet_text(l) for l in lines]
    vectors = [np.array(embed_model.get_text_embedding(t)) for t in texts]

    pairs = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            denom = np.linalg.norm(vectors[i]) * np.linalg.norm(vectors[j])
            sim = float(vectors[i].dot(vectors[j]) / denom) if denom else 0.0
            if sim > threshold:
                pairs.append((i, j, sim))
    return pairs


def _classify_pair(a: str, b: str) -> str:
    """Deterministic duplicate-vs-contradiction call for one related pair:
    a number that differs, or an explicit polarity-opposite keyword pair
    (allowed/blocked, always/never, ...), means the pair disagrees on a
    value -- a contradiction. Otherwise, two related sentences with no
    conflicting value are treated as saying the same thing -- a duplicate."""
    # Word-boundary numbers only -- a plain regex on \d+ also matches the
    # "5" inside "HW5" or the "1808" inside "s1808_rel", which caused a
    # false-positive contradiction between two lines that both just happen
    # to mention "HW5" (see AI_USE.md). Excluding digits immediately
    # preceded by a letter/digit/underscore keeps standalone values like
    # "12" or "9000" while skipping those embedded identifiers.
    num_pattern = r"(?<![A-Za-z0-9_])\d+"
    nums_a, nums_b = set(re.findall(num_pattern, a)), set(re.findall(num_pattern, b))
    if nums_a and nums_b and nums_a != nums_b:
        return "contradiction"
    if _has_polarity_conflict(a, b):
        return "contradiction"
    return "duplicate"


CONFIRM_DUPLICATE_PROMPT = """Do these two sentences state the same underlying fact (just phrased
differently), such that keeping only one of them loses no information?

1: {a}
2: {b}

Reply with exactly one word: YES or NO."""


def _confirm_duplicate(a: str, b: str) -> bool:
    """A narrow yes/no check before actually dropping a line as a
    duplicate -- embeddings alone flagged pairs that were merely related,
    not actually redundant (e.g. two different Course fields, or "the
    domain entity is Course" next to "the related entity is Department"),
    and silently dropping either would lose real information. This keeps
    the model's job small enough to trust: confirm or reject one candidate
    pair, not rewrite or classify a whole list."""
    result = get_model_client().complete(
        [{"role": "user", "content": CONFIRM_DUPLICATE_PROMPT.format(a=a, b=b)}]
    )
    return result["content"].strip().upper().startswith("Y")


def _classify_lines(lines: list[str]) -> dict:
    bullet_texts = [_bullet_text(l) for l in lines]
    related_pairs = _find_related_pairs(lines)

    duplicate_groups: list[list[int]] = []
    contradictions: list[list[int]] = []
    rejected_duplicate_candidates: list[list[int]] = []
    grouped: dict[int, int] = {}  # line index -> duplicate_groups index

    for i, j, _sim in related_pairs:
        kind = _classify_pair(bullet_texts[i], bullet_texts[j])
        if kind == "contradiction":
            contradictions.append([i + 1, j + 1])
            continue

        if not _confirm_duplicate(bullet_texts[i], bullet_texts[j]):
            rejected_duplicate_candidates.append([i + 1, j + 1])
            continue

        if i in grouped:
            duplicate_groups[grouped[i]].append(j + 1)
            grouped[j] = grouped[i]
        elif j in grouped:
            duplicate_groups[grouped[j]].append(i + 1)
            grouped[i] = grouped[j]
        else:
            duplicate_groups.append([i + 1, j + 1])
            grouped[i] = grouped[j] = len(duplicate_groups) - 1

    return {
        "duplicate_groups": duplicate_groups,
        "contradictions": contradictions,
        "rejected_duplicate_candidates": rejected_duplicate_candidates,
    }


def consolidate_memory_md(path: Path = MEMORY_PATH) -> dict:
    """Consolidation in three steps, each a task small enough for a 1.5B
    local model to do reliably (two earlier designs -- a one-shot full
    rewrite, then a one-shot JSON classification of the whole list -- both
    failed; see AI_USE.md):

    1. Embeddings find candidate pairs that are "about the same thing"
       (duplicates and contradictions both score high here); a
       deterministic check (differing numbers, or an explicit
       allowed/blocked-style antonym) decides which of the two a pair is,
       and a narrow yes/no model call confirms each duplicate candidate
       before anything gets dropped, so a merely-related pair (e.g. two
       different Course fields) doesn't silently lose information.
    2. Confirmed duplicate groups are collapsed deterministically (keep the
       first line in each group).
    3. Each contradiction pair gets its own small, focused call to merge
       into one line that explicitly says which value is current and what
       it replaced -- never silently dropped.
    """
    before_text = load_memory_md(path)
    before_lines = non_empty_non_comment_lines(before_text)
    before_count = len(before_lines)

    classification = _classify_lines(before_lines)
    duplicate_groups = classification["duplicate_groups"]
    contradictions = classification["contradictions"]
    rejected_duplicate_candidates = classification["rejected_duplicate_candidates"]

    drop_indices: set[int] = set()
    for group in duplicate_groups:
        for idx in sorted(group)[1:]:
            drop_indices.add(idx - 1)

    contradiction_resolutions: dict[int, str] = {}
    unresolved_flags: list[str] = []
    for pair in contradictions:
        if len(pair) != 2:
            continue
        i1, i2 = sorted(pair)
        a, b = _bullet_text(before_lines[i1 - 1]), _bullet_text(before_lines[i2 - 1])
        result = get_model_client().complete([
            {"role": "user", "content": RESOLVE_CONTRADICTION_PROMPT.format(a=a, b=b)}
        ])
        merged_line = result["content"].strip().splitlines()[0]
        contradiction_resolutions[i1 - 1] = merged_line
        drop_indices.add(i2 - 1)
        if "unresolved" in merged_line.lower() or "needs a human" in merged_line.lower():
            unresolved_flags.append(merged_line)

    final_lines = []
    for i, line in enumerate(before_lines):
        if i in contradiction_resolutions:
            final_lines.append(contradiction_resolutions[i])
        elif i in drop_indices:
            continue
        else:
            final_lines.append(_bullet_text(line))

    body = "# MEMORY.md - Durable Facts\n\n" + "\n".join(f"- {ln}" for ln in final_lines)
    timestamp = datetime.datetime.utcnow().isoformat(timespec="seconds")
    new_text = f"<!-- last_consolidated: {timestamp} -->\n{body}\n"
    path.write_text(new_text, encoding="utf-8")

    after_count = len(non_empty_non_comment_lines(new_text))
    return {
        "before_count": before_count,
        "after_count": after_count,
        "before_text": before_text,
        "after_text": new_text,
        "duplicate_groups": duplicate_groups,
        "contradictions": contradictions,
        "rejected_duplicate_candidates": rejected_duplicate_candidates,
        "contradiction_resolutions": list(contradiction_resolutions.values()),
        "unresolved_flags": unresolved_flags,
    }


DREAM_SYSTEM_PROMPT = """From this recent conversation, identify durable facts worth remembering
long-term (not small talk, not one-off requests) -- the kind of thing that
would still matter in a future, unrelated conversation. Reply with ONLY a
JSON array of short fact strings, e.g. ["fact one", "fact two"]. If there is
nothing durable worth keeping, reply with an empty array []."""


def dream(recent_conversation_text: str, path: Path = MEMORY_PATH) -> list[str]:
    """Extracts durable facts from recent_conversation_text and appends new
    ones (skipping near-exact duplicates already present) to MEMORY.md.
    Returns the facts actually added."""
    result = get_model_client().complete(
        [{"role": "system", "content": DREAM_SYSTEM_PROMPT},
         {"role": "user", "content": recent_conversation_text}],
        format="json",
    )
    try:
        parsed = json.loads(result["content"])
        if isinstance(parsed, dict):
            parsed = parsed.get("facts", [])
        if not isinstance(parsed, list):
            parsed = []
    except (json.JSONDecodeError, AttributeError):
        parsed = []

    existing = load_memory_md(path)
    existing_lower = existing.lower()
    added = []
    for fact in parsed:
        fact = str(fact).strip()
        if not fact or fact.lower() in existing_lower:
            continue
        added.append(fact)

    if added:
        with open(path, "a", encoding="utf-8") as f:
            for fact in added:
                f.write(f"- {fact}\n")

    return added
