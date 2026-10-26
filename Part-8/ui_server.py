"""
Part-8/ui_server.py -- DATA-260 HW7, Part 4.II (bike-share agent UI)

A small FastAPI app serving one page: a CSV upload field, a pricing URL
field, a Run button, a tool-call timeline panel, and a results panel
(decision, cost comparison, citations, step count, total time, stop
reason) -- everything POST /run returns from run_bikeshare_agent(), as
real JSON, not canned demo data.

Run (PORT_BASE+1, so it doesn't collide with Part-1's main.py on 8008):
    python ui_server.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from bikeshare_agent import run_bikeshare_agent
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import HTMLResponse

app = FastAPI(title="Bike-Share Membership Advisor")
PORT = 8009


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "ui_static" / "index.html").read_text(encoding="utf-8")


@app.post("/run")
async def run(question: str = Form(...), pricing_url: str = Form(...), csv_file: UploadFile = None):
    content = await csv_file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = run_bikeshare_agent(question, tmp_path, pricing_url)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ui_server:app", host="0.0.0.0", port=PORT, reload=False)
