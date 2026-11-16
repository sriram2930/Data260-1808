"""
Part-15/dashboard.py -- DATA-260 HW10, Part 1 (Streamlit operations dashboard)

Run:  streamlit run Part-15/dashboard.py

Pages
  Summary       request count, semantic-cache hit/miss split, error rate, end-to-end latency, stage latency.
                Each metric states its time window and data source.
  Evaluation    Part 2 per-case/per-stage judge scores; Part 3 judge validation (Spearman, MAD, repeatability).
  Trace lookup  paste a trace_id -> the request journey in stage order, hit / miss / failed path made explicit.

Data comes only from files the system itself writes (reports/hw10/raw/): spans.jsonl (one span per stage),
evaluations.jsonl, judge_validation.json, trace_examples.json, latency_experiment.json. Nothing is simulated.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tracing import RAW_DIR, STAGE_ORDER  # noqa: E402

SPANS = RAW_DIR / "spans.jsonl"
EVALS = RAW_DIR / "evaluations.jsonl"
VALIDATION = RAW_DIR / "judge_validation.json"
EXAMPLES = RAW_DIR / "trace_examples.json"
EXPERIMENT = RAW_DIR / "latency_experiment.json"

st.set_page_config(page_title="HW10 Operations Dashboard", layout="wide")


# --------------------------------------------------------------------------- cached loaders
def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(show_spinner=False)
def load_jsonl(path_str: str, mtime: float) -> pd.DataFrame:
    """mtime is part of the cache key, so the cache refreshes whenever the system appends to the file."""
    rows = []
    p = Path(path_str)
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_json(path_str: str, mtime: float):
    p = Path(path_str)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_resource(show_spinner=False)
def redis_client():
    """One shared Redis connection (expensive to rebuild on every rerun)."""
    import redis

    return redis.Redis(host="localhost", port=6379, socket_connect_timeout=1, socket_timeout=1)


def spans_df() -> pd.DataFrame:
    df = load_jsonl(str(SPANS), _mtime(SPANS))
    if df.empty:
        return df
    df = df.copy()
    df["path"] = df["attrs"].apply(lambda a: (a or {}).get("path"))
    df["cache_hit"] = df["attrs"].apply(lambda a: (a or {}).get("cache_hit"))
    df["failed_stage"] = df["attrs"].apply(lambda a: (a or {}).get("failed_stage"))
    return df


def pct(x: pd.Series, q: float) -> float:
    return float(np.percentile(x, q)) if len(x) else float("nan")


def fmt_ms(v: float) -> str:
    return "n/a" if v != v else (f"{v:,.0f} ms" if v < 10_000 else f"{v / 1000:,.1f} s")


# --------------------------------------------------------------------------- page 1
def page_summary() -> None:
    st.header("Summary")
    df = spans_df()
    if df.empty:
        st.warning("No spans yet. Send requests through Part-15/qa_service.py first.")
        return
    req = df[df["stage"] == "request"].copy()
    windows = {"Last 1 hour": 3600, "Last 6 hours": 6 * 3600, "Last 24 hours": 86400, "Last 7 days": 7 * 86400, "All recorded data": None}
    qp = st.query_params.get("window", "all")
    default_idx = {"1h": 0, "6h": 1, "24h": 2, "7d": 3}.get(qp, 4)  # ?window=1h preselects a window (used for screenshots)
    choice = st.sidebar.selectbox("Time window", list(windows), index=default_idx)
    if windows[choice]:
        req = req[req["end_ms"] >= (time.time() - windows[choice]) * 1000]
    lo, hi = (req["start_time"].min(), req["end_time"].max()) if len(req) else ("-", "-")
    window_txt = f"{choice} (requests from {lo[:19]} to {hi[:19]} UTC)"
    src = f"`{SPANS.relative_to(HERE.parent)}` (stage = request spans)"

    n = len(req)
    hits, misses = req[req["path"] == "cache_hit"], req[req["path"] == "cache_miss"]
    errs = req[req["status"] == "error"]
    served = req[req["path"].isin(["cache_hit", "cache_miss"])]  # real user requests; excludes injected malformed-input probes

    c = st.columns(4)
    c[0].metric("Requests", n)
    c[0].caption(f"Window: {window_txt}. Source: {src}.")
    rate = len(hits) / len(served) if len(served) else float("nan")
    c[1].metric("Semantic-cache hit rate", "n/a" if rate != rate else f"{rate:.1%}")
    c[1].caption(f"{len(hits)} hits / {len(served)} lookups that reached the cache. Same window and source. This includes the intentional 50-request all-miss latency experiment, so pick a narrower window for a traffic-mix view.")
    c[2].metric("Error rate", f"{len(errs) / n:.1%}" if n else "n/a")
    c[2].caption(f"{len(errs)} of {n} requests ended with status=error. Window and source as above.")
    ok_miss = misses[misses["status"] == "ok"]
    c[3].metric("Cache-miss end-to-end p50", fmt_ms(pct(ok_miss["duration_ms"], 50)))
    c[3].caption(f"p95 {fmt_ms(pct(ok_miss['duration_ms'], 95))}, n={len(ok_miss)} successful misses (request span: ingress to answer).")

    st.subheader("Cache hits vs cache misses (kept separate)")
    ok_hit = hits[hits["status"] == "ok"]
    tab = pd.DataFrame([
        {"path": "cache HIT (served from Redis, no Kafka)", "requests": len(hits), "ok": int((hits["status"] == "ok").sum()),
         "errors": int((hits["status"] == "error").sum()), "p50 latency": fmt_ms(pct(ok_hit["duration_ms"], 50)),
         "p95 latency": fmt_ms(pct(ok_hit["duration_ms"], 95)), "mean latency": fmt_ms(float(ok_hit["duration_ms"].mean()) if len(ok_hit) else float("nan"))},
        {"path": "cache MISS (Planner -> Writer -> Reviewer over Kafka)", "requests": len(misses), "ok": len(ok_miss),
         "errors": int((misses["status"] == "error").sum()), "p50 latency": fmt_ms(pct(ok_miss["duration_ms"], 50)),
         "p95 latency": fmt_ms(pct(ok_miss["duration_ms"], 95)), "mean latency": fmt_ms(float(ok_miss["duration_ms"].mean()) if len(ok_miss) else float("nan"))},
    ])
    st.dataframe(tab, hide_index=True, use_container_width=True)
    st.caption(f"Window: {window_txt}. Source: {src}. Latency = request span; hit latency is never averaged into miss latency.")

    if len(ok_miss):
        st.subheader("Stage latency on successful cache misses")
        ids = set(ok_miss["trace_id"])
        sp = df[df["trace_id"].isin(ids)]
        rows = []
        qtot = sp[sp["stage"].str.startswith("queue_")].groupby("trace_id")["duration_ms"].sum()
        for stage in ["cache_lookup", "facts_lookup", "planner", "writer", "reviewer"]:
            x = sp[sp["stage"] == stage]["duration_ms"]
            rows.append({"stage": stage, "n": len(x), "p50 (ms)": round(pct(x, 50), 1), "p95 (ms)": round(pct(x, 95), 1)})
        rows.append({"stage": "queue wait (total of 4 queues)", "n": len(qtot), "p50 (ms)": round(pct(qtot, 50), 1), "p95 (ms)": round(pct(qtot, 95), 1)})
        ev = sp[sp["stage"] == "evaluation"].sort_values("start_ms").drop_duplicates("trace_id", keep="last")["duration_ms"]  # re-runs: latest span only
        if len(ev):
            rows.append({"stage": "evaluation (offline judge)", "n": len(ev), "p50 (ms)": round(pct(ev, 50), 1), "p95 (ms)": round(pct(ev, 95), 1)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(f"Window: {window_txt}. Source: {src}, joined on trace_id. The full 50-request experiment is in the report (Part 4.3).")

    try:
        n_cached = sum(1 for _ in redis_client().scan_iter(match="s1808:semcache:*"))
        st.caption(f"Live Redis: {n_cached} entries under the s1808:semcache: prefix right now (not windowed).")
    except Exception:  # noqa: BLE001 -- Redis may be stopped; the dashboard must still render
        st.caption("Live Redis cache size unavailable (Redis not reachable).")


# --------------------------------------------------------------------------- page 2
def page_evaluation() -> None:
    st.header("Evaluation")
    ev = load_jsonl(str(EVALS), _mtime(EVALS))
    st.subheader("Part 2: pipeline evaluation (judge: qwen3:8b, 1-5 scale)")
    if ev.empty:
        st.info("No evaluation records yet. Run `python Part-15/evaluator.py --pending`.")
    else:
        ev = ev.drop_duplicates("trace_id", keep="last")
        okev = ev[ev["status"] == "ok"].copy()
        okev["Plan"] = okev["plan_quality"].apply(lambda d: d["score"])
        okev["Writer draft"] = okev["writer_helpfulness"].apply(lambda d: d["score"])
        okev["Final answer"] = okev["final_helpfulness"].apply(lambda d: d["score"])
        okev["Final - draft"] = okev["improvement"].apply(lambda d: d["difference"])
        okev["draft"] = okev["draft"].fillna("")
        okev["final"] = okev["final"].fillna("")
        st.caption(f"Source: `{EVALS.relative_to(HERE.parent)}`, {len(ev)} evaluated trace(s), {len(ev) - len(okev)} with errors. Window: all records.")
        cols = st.columns(4)
        for col, name in zip(cols, ["Plan", "Writer draft", "Final answer", "Final - draft"]):
            col.metric(f"Mean: {name}", f"{okev[name].mean():+.2f}" if name == "Final - draft" else f"{okev[name].mean():.2f}")
        st.markdown("**Scores by case and pipeline stage**")
        show = okev[["question", "Plan", "Writer draft", "Final answer", "Final - draft"]].copy()
        show["Reviewer changed text?"] = okev.apply(lambda r: "no (verbatim)" if r["draft"].strip() == r["final"].strip() else "rewritten", axis=1)
        show["trace_id"] = okev["trace_id"]
        st.dataframe(show, hide_index=True, use_container_width=True, height=420,
                     column_config={"question": st.column_config.TextColumn(width="large"), "trace_id": st.column_config.TextColumn(width="medium")})
        long = okev.melt(id_vars=["trace_id"], value_vars=["Plan", "Writer draft", "Final answer"], var_name="stage", value_name="score")
        dist = long.groupby(["stage", "score"]).size().reset_index(name="cases")
        st.altair_chart(alt.Chart(dist).mark_bar().encode(
            x=alt.X("score:O", title="judge score (1-5)"), y=alt.Y("cases:Q", title="number of traces"),
            color=alt.Color("stage:N", sort=["Plan", "Writer draft", "Final answer"]), xOffset="stage:N",
            tooltip=["stage", "score", "cases"]), use_container_width=True)
        up, same, down = int((okev["Final - draft"] > 0).sum()), int((okev["Final - draft"] == 0).sum()), int((okev["Final - draft"] < 0).sum())
        verbatim = int((show["Reviewer changed text?"] == "no (verbatim)").sum())
        mp, mw, mf = okev["Plan"].mean(), okev["Writer draft"].mean(), okev["Final answer"].mean()
        st.markdown(
            f"**Interpretation.** Mean scores: Planner {mp:.2f}, Writer {mw:.2f}, Reviewer final {mf:.2f} (n={len(okev)}). "
            f"The Planner is the strongest stage; the Writer scores {mp - mw:.2f} below the plan it was given, so the weak link is the Writer's "
            f"execution of a good plan, not the plan itself. The Reviewer left the text unchanged in {verbatim} of {len(okev)} traces and, by score, "
            f"improved {up}, matched {same} and worsened {down} (mean final - draft = {okev['Final - draft'].mean():+.2f}). "
            "Coordination holds (every stage received and used the previous stage's output), but the review step adds little measurable value "
            "on this judge: the final answer is not meaningfully better than the draft.")
        with st.expander("Full records (message metadata, reasons, judge settings)"):
            st.json(okev.drop(columns=["Plan", "Writer draft", "Final answer", "Final - draft"]).tail(3).to_dict("records"))

    st.subheader("Part 3: is the judge reliable?")
    v = load_json(str(VALIDATION), _mtime(VALIDATION))
    if not v:
        st.info("Judge validation not run yet (Part-15/validate_judge.py).")
        return
    st.caption(f"Source: `{VALIDATION.relative_to(HERE.parent)}`. {v['n_cases']} frozen cases scored against hand-assigned human labels.")
    cols = st.columns(4)
    cols[0].metric("Spearman rho (human vs judge)", f"{v['spearman_rho']:.3f}" if v["spearman_rho"] is not None else "undefined")
    cols[0].caption(f"p = {v['spearman_p']:.3g}" if v["spearman_p"] is not None else "constant scores")
    cols[1].metric("Mean absolute difference", f"{v['mean_abs_diff']:.2f}")
    cols[1].caption("on the 1-5 scale")
    rp = v["repeatability"]
    cols[2].metric("Cases whose score changed", f"{rp['cases_changed']} / {v['n_cases']}")
    cols[2].caption(f"{rp['n_runs']} runs, same inputs and settings")
    cols[3].metric("Change size (mean / max abs)", f"{rp['mean_abs_change']:.2f} / {rp['max_abs_change']}")
    cols[3].caption("across repeated runs")
    df = pd.DataFrame(v["per_case"])
    st.dataframe(df, hide_index=True, use_container_width=True, height=(len(df) + 1) * 35 + 3)
    st.markdown(f"**Verdict.** {v['verdict']}")


# --------------------------------------------------------------------------- page 3
def page_trace() -> None:
    st.header("Trace lookup")
    df = spans_df()
    ex = load_json(str(EXAMPLES), _mtime(EXAMPLES)) or {}
    st.caption(f"Data source: `{SPANS.relative_to(HERE.parent)}` (one span per stage, trace_id = HW8 correlation_id).")
    if ex:
        st.markdown("Required example traces (click to load):")
        c = st.columns(3)
        for col, (label, key) in zip(c, [("Cache hit", "cache_hit"), ("Cache miss (completed)", "cache_miss_success"), ("Failed", "failed")]):
            if col.button(f"{label}: {ex[key][:8]}"):
                st.session_state["trace_id"] = ex[key]
    tid = st.text_input("trace_id", key="trace_id", placeholder="paste a trace_id").strip()
    if not tid:
        return
    if df.empty or tid not in set(df["trace_id"].dropna()):
        st.error(f"No spans found for trace_id {tid}.")
        return
    t = df[df["trace_id"] == tid].copy()
    t["_order"] = t["stage"].apply(lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 99)
    total = t[t["stage"] == "request"]
    journey = t[t["stage"] != "request"].sort_values(["start_ms", "_order"])
    journey = pd.concat([journey, total])
    t0 = float(t["start_ms"].min())

    lookup = t[t["stage"] == "cache_lookup"]
    hit = bool(lookup["cache_hit"].iloc[0]) if len(lookup) else False
    failed = t[t["status"] == "error"]
    if len(failed):
        bad = failed[failed["stage"] != "request"]
        stage = bad["stage"].iloc[0] if len(bad) else "request"
        st.error(f"FAILED PATH: stage `{stage}` failed. Error: {failed['error'].dropna().iloc[0] if failed['error'].notna().any() else 'n/a'}")
    elif hit:
        st.success("CACHE HIT PATH: answered from the semantic cache. No Kafka stage ran (no queue/planner/writer/reviewer spans).")
    else:
        st.info("CACHE MISS PATH: cache_lookup missed, then the request travelled inbox -> planner -> tasks -> writer -> drafts -> reviewer -> final.")

    out = pd.DataFrame({
        "#": range(1, len(journey) + 1),
        "stage": journey["stage"].values,
        "start time (UTC)": journey["start_time"].str.slice(11, 23).values,
        "end time (UTC)": journey["end_time"].str.slice(11, 23).values,
        "duration (ms)": journey["duration_ms"].round(1).values,
        "status": journey["status"].values,
        "detail": journey["attrs"].apply(lambda a: ", ".join(f"{k}={v}" for k, v in (a or {}).items()
                                                            if v not in (None, "") and k in ("cache_hit", "similarity", "path", "failed_stage", "attempts", "matched_query"))).values,
        "error": journey["error"].fillna("").values,
    })
    st.dataframe(out, hide_index=True, use_container_width=True, height=(len(out) + 1) * 35 + 3,
                 column_config={"error": st.column_config.TextColumn(width="large"), "detail": st.column_config.TextColumn(width="medium")})
    gantt = pd.DataFrame({"stage": journey["stage"].values, "start": (journey["start_ms"].values - t0),
                          "end": (journey["end_ms"].values - t0), "status": journey["status"].values})
    gantt["end"] = gantt[["end"]].max(axis=1).where(gantt["end"] > gantt["start"] + 0.5, gantt["start"] + 0.5)
    st.altair_chart(alt.Chart(gantt).mark_bar().encode(
        y=alt.Y("stage:N", sort=list(gantt["stage"]), title=None), x=alt.X("start:Q", title="ms since request start"), x2="end:Q",
        color=alt.Color("status:N", scale=alt.Scale(domain=["ok", "error"], range=["#2a9d8f", "#d1495b"])),
        tooltip=["stage", "start", "end", "status"]), use_container_width=True)
    evs = load_jsonl(str(EVALS), _mtime(EVALS))
    if not evs.empty and tid in set(evs["trace_id"]):
        r = evs[evs["trace_id"] == tid].iloc[-1]
        if r["status"] == "ok":
            st.markdown(f"**Judge scores for this trace:** plan {r['plan_quality']['score']}, draft {r['writer_helpfulness']['score']}, "
                        f"final {r['final_helpfulness']['score']}. {r['improvement']['interpretation']}")


PAGES = {"Summary": page_summary, "Evaluation": page_evaluation, "Trace lookup": page_trace}
st.sidebar.title("HW10 dashboard")
st.sidebar.caption("Sreeramachandrasai Achutuni | SID 019151808 | PREFIX s1808")
page = st.sidebar.radio("Page", list(PAGES))
if st.sidebar.button("Reload data"):
    st.cache_data.clear()
PAGES[page]()
