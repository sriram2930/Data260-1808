"""
Part-2/agent_graph.py -- DATA-260 HW2, Parts 3 & 4 (Stateful Agent Graph +
Output Schema and Loop Safety)

Refactors the HW1 Planner -> Reviewer -> Finalizer waterfall (agents_demo.py)
into a stateful LangGraph graph implementing the supervisor pattern: a
Supervisor node routes between Planner and Reviewer nodes, and the graph can
loop back for self-correction (a rejected proposal, or one that fails Pydantic
schema validation) up to a configurable turn ceiling, instead of always
running exactly twice and stopping.

All LLM calls happen through Part-4/src/model_client.py's ModelClient adapter
(not langchain / not the raw ollama client directly), per the assignment.

Graph shape:

    START -> supervisor -(router_logic)-> planner | reviewer | END
    planner  -> supervisor
    reviewer -> supervisor

`router_logic` decides where to go next:
  - if the Reviewer already approved a proposal -> END (success)
  - if there is a fresh, schema-valid proposal that hasn't been reviewed yet
    -> reviewer (review it, regardless of the ceiling -- a valid last attempt
    still deserves review)
  - if the planner-attempt ceiling (`turn_ceiling`) has been reached -> END
    (abandoned)
  - otherwise -> planner (first attempt, a validation-failure retry, or a
    reviewer-rejection retry)

`turn_count` is incremented inside planner_node once per Planner attempt, so
it directly answers "how many Planner attempts did this run take" -- which is
exactly what Part 4's four-way run classification needs.

Usage:
    python agent_graph.py --input-file cases/schema_input.json --turn-ceiling 10
    python agent_graph.py --input-file cases/schema_input.json --force-reviewer-issues
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field, ValidationError, field_validator

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent

# ModelClient lives in the sibling Part-4/ folder (HW1's model-adapter module).
sys.path.insert(0, str(REPO_ROOT / "Part-4"))
from src.model_client import ModelClient, DEFAULT_MODEL  # noqa: E402

from langgraph.graph import StateGraph, END  # noqa: E402

DEFAULT_TURN_CEILING = 4


# --------------------------------------------------------------------------
# Step 4.1 -- Pydantic schema for the Planner's output. Distinct from HW1's
# `PlannerOutput` (which relied on langchain's schema-constrained generation
# to *guarantee* the shape): here the model only gets Ollama's basic JSON
# mode (syntactically valid JSON, no shape guarantee), so this validator can
# genuinely fail -- which is the point, since Part 4 measures what happens
# when it does.
# --------------------------------------------------------------------------

class PlannerTags(BaseModel):
    tags: List[str] = Field(description="Exactly 3 short topical tags.")
    summary: str = Field(description="One sentence, at most 25 words.")

    @field_validator("tags")
    @classmethod
    def check_tags(cls, v: List[str]) -> List[str]:
        if len(v) != 3:
            raise ValueError(f"must have exactly 3 tags, got {len(v)}")
        for t in v:
            if not (3 <= len(t) <= 30):
                raise ValueError(f"tag {t!r} must be 3-30 characters, got {len(t)}")
        return v

    @field_validator("summary")
    @classmethod
    def check_summary(cls, v: str) -> str:
        n = len(v.split())
        if n > 25:
            raise ValueError(f"summary must be at most 25 words, got {n}")
        return v


PLANNER_SYSTEM_PROMPT = """You are the Planner in a multi-agent content-tagging system.
Given a TITLE and CONTENT, respond with ONLY a JSON object of the exact shape:
{"tags": ["tag1", "tag2", "tag3"], "summary": "..."}
Rules: exactly 3 tags, each 3-30 characters; summary is one sentence, at most 25
words. Base tags and summary strictly on the given TITLE and CONTENT -- do not
invent facts, and do not assume any particular subject domain in advance."""

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer in a multi-agent content-tagging system.
You will be given the original TITLE and CONTENT, plus a Planner's proposed tags
and summary. Respond with ONLY a JSON object of the exact shape:
{"approved": true|false, "issues": ["...", ...]}
Approve (true, empty issues list) only if all 3 tags are specific and genuinely
relevant (not vague filler like "general" or "misc") and the summary is a single,
faithful sentence of at most 25 words. Otherwise return approved=false and a short
list of concrete issues to fix."""


# --------------------------------------------------------------------------
# Step 2 -- Shared state
# --------------------------------------------------------------------------

class AgentState(TypedDict):
    title: str
    content: str
    email: str
    strict: bool
    task: str
    llm: Any
    planner_proposal: Optional[Dict[str, Any]]
    reviewer_feedback: Optional[Dict[str, Any]]
    turn_count: int
    turn_ceiling: int
    validation_error: Optional[str]
    force_reviewer_issues: bool


# --------------------------------------------------------------------------
# Step 3 -- Nodes
# --------------------------------------------------------------------------

def planner_node(state: AgentState) -> Dict[str, Any]:
    turn = state.get("turn_count", 0) + 1
    print(f"---NODE: Planner (attempt {turn}/{state['turn_ceiling']})---")

    client: ModelClient = state["llm"]
    user_block = f"TITLE: {state['title']}\n\nCONTENT: {state['content']}"

    if state.get("validation_error"):
        user_block += (
            f"\n\nYour previous attempt was INVALID: {state['validation_error']}\n"
            "Fix this and respond again with ONLY the corrected JSON object."
        )
    feedback = state.get("reviewer_feedback")
    if feedback and not feedback.get("approved", True):
        user_block += (
            f"\n\nThe Reviewer rejected your previous proposal for these reasons: "
            f"{feedback.get('issues', [])}\nAddress them and respond again with ONLY "
            "the corrected JSON object."
        )

    response = client.complete(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ],
        format="json",
    )

    try:
        parsed = json.loads(response["content"])
        validated = PlannerTags(**parsed)
        print(f"  -> valid proposal: {validated.tags}")
        return {
            "planner_proposal": validated.model_dump(),
            "validation_error": None,
            "turn_count": turn,
        }
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        print(f"  -> INVALID: {e}")
        return {
            "planner_proposal": None,
            "validation_error": str(e),
            "turn_count": turn,
        }


def reviewer_node(state: AgentState) -> Dict[str, Any]:
    print("---NODE: Reviewer---")

    if state.get("force_reviewer_issues"):
        # Test hook for the Part 3 Step 6 correction-loop demonstration: force
        # a rejection (no LLM call needed) and confirm the graph routes back
        # to the Planner.
        print("  -> (forced) rejecting to test the correction loop")
        return {
            "reviewer_feedback": {"approved": False, "issues": ["forced rejection for testing"]},
            "planner_proposal": None,
        }

    client: ModelClient = state["llm"]
    proposal = state["planner_proposal"]
    user_block = (
        f"TITLE: {state['title']}\n\nCONTENT: {state['content']}\n\n"
        f"PLANNER TAGS: {json.dumps(proposal['tags'])}\n"
        f"PLANNER SUMMARY: {proposal['summary']}"
    )
    response = client.complete(
        [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ],
        format="json",
    )

    try:
        feedback = json.loads(response["content"])
        approved = bool(feedback.get("approved"))
    except json.JSONDecodeError:
        # Treat unparsable Reviewer output as a rejection so the graph keeps
        # making forward progress (another Planner retry) instead of crashing.
        feedback = {"approved": False, "issues": ["reviewer output was not valid JSON"]}
        approved = False

    print(f"  -> approved={approved} issues={feedback.get('issues', [])}")
    if approved:
        return {"reviewer_feedback": feedback}
    return {"reviewer_feedback": feedback, "planner_proposal": None}


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    print(f"---NODE: Supervisor (turn_count={state.get('turn_count', 0)}, "
          f"ceiling={state['turn_ceiling']})---")
    return {}


def router_logic(state: AgentState) -> str:
    feedback = state.get("reviewer_feedback")
    if feedback and feedback.get("approved"):
        return END
    if state.get("planner_proposal") is not None and not state.get("validation_error"):
        # A fresh, schema-valid, not-yet-reviewed proposal exists -- always
        # let the Reviewer weigh in on it, even if this was the ceiling-th
        # Planner attempt.
        return "reviewer"
    if state.get("turn_count", 0) >= state.get("turn_ceiling", DEFAULT_TURN_CEILING):
        return END
    return "planner"


# --------------------------------------------------------------------------
# Step 5 -- Assemble the graph
# --------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor", router_logic, {"planner": "planner", "reviewer": "reviewer", END: END}
    )
    graph.add_edge("planner", "supervisor")
    graph.add_edge("reviewer", "supervisor")
    return graph.compile()


def classify_outcome(final_state: AgentState) -> str:
    """One of the four Part-4.3 buckets."""
    feedback = final_state.get("reviewer_feedback")
    approved = bool(feedback and feedback.get("approved"))
    turns = final_state.get("turn_count", 0)
    if not approved:
        return "hit_turn_ceiling"
    if turns <= 1:
        return "valid_first_attempt"
    if turns == 2:
        return "valid_after_1_retry"
    return "valid_after_2plus_retries"


def run_graph(
    title: str,
    content: str,
    turn_ceiling: int = DEFAULT_TURN_CEILING,
    model: str = DEFAULT_MODEL,
    temperature: Optional[float] = None,
    force_reviewer_issues: bool = False,
    stream: bool = False,
) -> dict:
    """Compile and invoke the graph once. Returns the final state plus timing
    and the outcome classification, so callers (CLI or the Part-4 experiment
    runners) can both print a transcript and log raw metrics."""
    compiled = build_graph()
    client = ModelClient(model=model, temperature=temperature)

    initial_state: AgentState = {
        "title": title,
        "content": content,
        "email": "",
        "strict": True,
        "task": "tag_and_summarize",
        "llm": client,
        "planner_proposal": None,
        "reviewer_feedback": None,
        "turn_count": 0,
        "turn_ceiling": turn_ceiling,
        "validation_error": None,
        "force_reviewer_issues": force_reviewer_issues,
    }

    t0 = time.perf_counter()
    final_state = dict(initial_state)
    if stream:
        for step in compiled.stream(initial_state):
            for node_name, update in step.items():
                if update:
                    final_state.update(update)
    else:
        final_state = compiled.invoke(initial_state)
    latency_ms = (time.perf_counter() - t0) * 1000

    outcome = classify_outcome(final_state)
    return {
        "final_state": {k: v for k, v in final_state.items() if k != "llm"},
        "outcome": outcome,
        "latency_ms": latency_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stateful Planner/Reviewer graph (LangGraph)")
    parser.add_argument("--title")
    parser.add_argument("--content")
    parser.add_argument("--input-file", help='JSON file with {"title": ..., "content": ...}')
    parser.add_argument("--turn-ceiling", type=int, default=DEFAULT_TURN_CEILING)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument(
        "--force-reviewer-issues",
        action="store_true",
        help="Test hook: make the Reviewer always reject, to demonstrate the correction loop.",
    )
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

    result = run_graph(
        title=title,
        content=content,
        turn_ceiling=args.turn_ceiling,
        model=args.model,
        temperature=args.temperature,
        force_reviewer_issues=args.force_reviewer_issues,
        stream=True,
    )

    print("\n=== FINAL STATE ===")
    print(json.dumps(result["final_state"], indent=2))
    print(f"\nOutcome: {result['outcome']}")
    print(f"Latency: {result['latency_ms']:.1f} ms")


if __name__ == "__main__":
    main()
