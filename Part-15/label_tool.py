"""
Part-15/label_tool.py -- DATA-260 HW10, Part 3.1 (one-click human labeling)

Run:  streamlit run Part-15/label_tool.py

Shows one Writer draft at a time (question, the facts the Writer was given, the draft) and records YOUR 1-5
helpfulness label into Part-15/human_labels.csv. It deliberately shows no judge score and no suggested label.
Guide: 5 = accurate, complete, relevant, clear; 4 = good, minor weakness; 3 = partly helpful / incomplete / padded / minor error;
       2 = mostly unhelpful or significant error; 1 = wrong or irrelevant. Judge accuracy against the FACTS.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

import csv
import json
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "eval_cases.json").read_text(encoding="utf-8"))
LABELS = HERE / "human_labels.csv"

st.set_page_config(page_title="HW10 labeling", layout="centered")


def load() -> dict:
    with LABELS.open(encoding="utf-8") as fh:
        return {r["case_id"]: r["human_label"] for r in csv.DictReader(fh)}


def save(labels: dict) -> None:
    with LABELS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "human_label"])
        for c in CASES:
            w.writerow([c["case_id"], labels.get(c["case_id"], "")])


labels = load()
done = sum(1 for v in labels.values() if v.strip())
st.title("Label the Writer drafts")
st.progress(done / len(CASES), text=f"{done} of {len(CASES)} labeled")
st.caption("5 = accurate, complete, relevant, clear | 4 = good, minor weakness | 3 = partly helpful / incomplete / minor error | "
           "2 = mostly unhelpful or significant error | 1 = wrong or irrelevant. Judge accuracy against the facts.")

idx = st.session_state.get("idx", next((i for i, c in enumerate(CASES) if not labels.get(c["case_id"], "").strip()), 0))
idx = max(0, min(idx, len(CASES) - 1))
c = CASES[idx]
st.subheader(f"{c['case_id']} ({idx + 1}/{len(CASES)})")
st.markdown(f"**Question:** {c['question']}")
st.markdown("**Facts the Writer was given:**")
for f in c["facts"] or ["(no catalogue facts matched this question)"]:
    st.markdown(f"- {f}")
st.markdown("**Writer draft:**")
st.info(c["draft"])
current = labels.get(c["case_id"], "").strip()
if current:
    st.caption(f"Current label: {current}")

cols = st.columns(5)
for n, col in zip(range(1, 6), cols):
    if col.button(str(n), key=f"b{n}", use_container_width=True):
        labels[c["case_id"]] = str(n)
        save(labels)
        st.session_state["idx"] = min(idx + 1, len(CASES) - 1)
        st.rerun()
nav = st.columns(2)
if nav[0].button("Previous") and idx > 0:
    st.session_state["idx"] = idx - 1
    st.rerun()
if nav[1].button("Skip / next") and idx < len(CASES) - 1:
    st.session_state["idx"] = idx + 1
    st.rerun()
if done == len(CASES):
    st.success("All 20 labeled and saved to Part-15/human_labels.csv. Tell Claude you are done.")
