"""
Part-7/inspect_tools.py -- DATA-260 HW5, Part 2 (scripted MCP Inspector
equivalent, for a machine-readable raw record)

Calls every tool on both servers over the real MCP STDIO protocol (the same
protocol the MCP Inspector UI drives interactively), using the MCP Python
SDK's own client. This produces the machine-readable "MCP Inspector test
outputs for all tools" the HW5 repository instructions ask for in
reports/hw05/raw/ -- the actual labeled screenshots of the Inspector's
browser UI are a separate, manual step (`mcp dev <file>.py`), not something
a script can produce, so this covers the raw-data side of that requirement.

Run:
    python inspect_tools.py
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = Path(__file__).parent
RAW_DIR = HERE.parent / "reports" / "hw05" / "raw"


async def call_tool(session: ClientSession, name: str, args: dict) -> dict:
    result = await session.call_tool(name, args)
    content = [c.model_dump() for c in result.content]
    return {"tool": name, "args": args, "isError": result.isError, "content": content}


PYTHON = str(HERE.parent / ".venv" / "Scripts" / "python.exe")


async def inspect_server(script: str, calls: list[tuple[str, dict]]) -> list[dict]:
    params = StdioServerParameters(command=PYTHON, args=[str(HERE / script)])
    records = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            records.append({"server": script, "tools": [t.name for t in tools.tools]})
            for name, args in calls:
                record = await call_tool(session, name, args)
                record["server"] = script
                records.append(record)
    return records


async def main() -> None:
    meals_calls = [
        ("search_meals_by_name", {"query": "Arrabiata", "limit": 3}),
        ("meals_by_ingredient", {"ingredient": "chicken", "limit": 3}),
        ("random_meal", {}),
        ("meal_details", {"id": "52772"}),
    ]
    domain_calls = [
        ("search_courses", {"query": "Cloud Computing", "limit": 3}),
        ("search_courses", {"query": "", "limit": 3}),  # invalid
        ("course_detail", {"course_id": 7}),
        ("course_detail", {"course_id": 999999}),  # invalid
        ("department_stats", {"department_id": 1}),
        ("department_stats", {"department_id": 999999}),  # invalid
    ]

    all_records = []
    all_records.extend(await inspect_server("meals_server.py", meals_calls))
    all_records.extend(await inspect_server("domain_server.py", domain_calls))

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "mcp_inspector_outputs.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "records": all_records},
            f,
            indent=2,
        )
    print(f"Wrote {out_path}")
    for r in all_records:
        print(json.dumps(r, indent=2)[:500])


if __name__ == "__main__":
    asyncio.run(main())
