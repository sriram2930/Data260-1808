# AI_USE.md — HW2

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code for the actual implementation work: designing and writing the
FastAPI CRUD backend (`Part-1/main.py` + templates), the responsive/stateful CSS,
the LangGraph supervisor-pattern refactor of the Planner/Reviewer agents
(`Part-2/agent_graph.py`), the Pydantic schema-validation + retry logic, and the
three Part-4 experiment runners. It also ran everything end-to-end on this
machine (starting the FastAPI server, invoking the graph, running the 30/20/20/5
experiment batches against the real local Ollama model) rather than just writing
code and assuming it worked.

What I did myself: decided the overall folder mapping (which HW2 part extends
which existing HW1 folder), chose to keep AWS/Docker deployment separate from
this homework's scope, reviewed the generated FastAPI/graph behavior by hand
before accepting it, and made the final calls on things like which fixed input
to use for the 30-run classification experiment versus the adversarial input.

## 2. One AI-produced output that was wrong/unsuitable

The first version of the FastAPI home route called
`templates.TemplateResponse("home.html", {"request": request, ...})` — the
"classic" Starlette calling convention. The version of Starlette actually
installed in this environment (pulled in transitively by the current FastAPI
release) changed that signature to `TemplateResponse(request, name, context)`,
request first. The old call order silently passed the context dict into the
`name` parameter, which crashed with `TypeError: unhashable type: 'dict'` deep
inside Jinja2's template cache lookup — a confusing error that doesn't obviously
point at "wrong argument order" from the traceback alone.

A second, similar issue: `supervisor_node` in the LangGraph graph returns `{}`
when it has no state to update. When streaming the graph with `.stream()`, that
empty-dict update comes back as `None` rather than `{}`, and the transcript
printer's `final_state.update(update)` crashed with
`TypeError: 'NoneType' object is not iterable` on the very first supervisor step.

## 3. How I detected the problem / verified the result

Both were caught immediately by actually running the code against the real
stack — starting `uvicorn` and hitting the endpoint with `curl` for the first
one, and running `agent_graph.py` end-to-end against the real local Ollama model
for the second — rather than treating "the code looks right" as sufficient. In
both cases the traceback was printed straight to the console, and the fix was
verified by re-running the exact same command and confirming a clean result
(HTTP 200 with the expected page content; the graph completing a full
Planner→Reviewer→Planner correction loop without crashing).

## 4. What I changed and why it works now

- Fixed both `TemplateResponse` call sites in `Part-1/main.py` to
  `templates.TemplateResponse(request, "home.html", {...})` /
  `templates.TemplateResponse(request, "edit.html", {...})` — request first,
  context without a redundant `"request"` key (Starlette adds it automatically
  via `context.setdefault`). Re-verified: home page and edit page both return
  HTTP 200 and render correctly.
- Guarded the graph-streaming loop in `agent_graph.run_graph()` with
  `if update: final_state.update(update)`, so a node's empty/`None` update no
  longer crashes the transcript. Re-verified: a full run (including the forced
  correction-loop test) streams and completes cleanly, printing every node's
  state transition as intended.

A separate, non-bug finding worth recording here too: the small local model
(`qwen2.5:1.5b-instruct`) genuinely fails the Pydantic schema check often enough
for the retry logic to matter — on the original, longer course-description
input it failed the 25-word summary limit on 6 consecutive attempts across two
separate runs (100% ceiling-hit), which is why that input became the
**adversarial** case (`reports/hw02/cases/adversarial_input.json`) instead of the
main classification input; a shorter, simpler input was used for the 30-run
experiment so the four outcome buckets would show real variety rather than
degenerating to "always hits the ceiling."
