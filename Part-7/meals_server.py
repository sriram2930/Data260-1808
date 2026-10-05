"""
Part-7/meals_server.py -- DATA-260 HW5, Part 2.A (TheMealDB tutorial MCP server)

A local MCP server named "meals" over TheMealDB's public API, run via STDIO
with FastMCP. Four tools: search_meals_by_name, meals_by_ingredient,
random_meal, meal_details. No API key needed -- TheMealDB's published test
key "1" is used directly in the base URL.

STDIO logging rule: never print to stdout (it corrupts the JSON-RPC stream
FastMCP uses to talk to the client/Inspector). All logging here goes to
stderr via the logging module.

Run and debug with the MCP Inspector:
    mcp dev meals_server.py
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s meals_server: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("meals_server")

BASE_URL = "https://www.themealdb.com/api/json/v1/1"

mcp = FastMCP("meals")


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}/{path}"
    log.info("GET %s params=%s", path, params)
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        log.error("request to %s failed: %s", path, exc)
        raise RuntimeError(f"TheMealDB request failed: {exc}") from exc


def _meal_card(m: dict) -> dict:
    return {
        "id": m.get("idMeal"),
        "name": m.get("strMeal"),
        "area": m.get("strArea"),
        "category": m.get("strCategory"),
        "thumb": m.get("strMealThumb"),
    }


def _small_card(m: dict) -> dict:
    return {
        "id": m.get("idMeal"),
        "name": m.get("strMeal"),
        "thumb": m.get("strMealThumb"),
    }


def _ingredients(m: dict) -> list[dict]:
    out = []
    for i in range(1, 21):
        name = (m.get(f"strIngredient{i}") or "").strip()
        measure = (m.get(f"strMeasure{i}") or "").strip()
        if name:
            out.append({"name": name, "measure": measure})
    return out


def _full_details(m: dict) -> dict:
    return {
        "id": m.get("idMeal"),
        "name": m.get("strMeal"),
        "category": m.get("strCategory"),
        "area": m.get("strArea"),
        "instructions": m.get("strInstructions"),
        "image": m.get("strMealThumb"),
        "source": m.get("strSource"),
        "youtube": m.get("strYoutube"),
        "ingredients": _ingredients(m),
    }


@mcp.tool()
def search_meals_by_name(query: str, limit: int = 5) -> dict[str, Any]:
    """Search TheMealDB for meals by name. Returns up to `limit` meal cards."""
    limit = max(1, min(25, limit))
    data = _get("search.php", {"s": query})
    meals = data.get("meals")
    if not meals:
        return {"count": 0, "message": "no matches", "meals": []}
    cards = [_meal_card(m) for m in meals[:limit]]
    return {"count": len(cards), "message": None, "meals": cards}


@mcp.tool()
def meals_by_ingredient(ingredient: str, limit: int = 12) -> dict[str, Any]:
    """Filter TheMealDB meals by main ingredient. Returns up to `limit` small cards."""
    limit = max(1, min(50, limit))
    data = _get("filter.php", {"i": ingredient})
    meals = data.get("meals")
    if not meals:
        return {"count": 0, "message": "no matches", "meals": []}
    cards = [_small_card(m) for m in meals[:limit]]
    return {"count": len(cards), "message": None, "meals": cards}


@mcp.tool()
def random_meal() -> dict[str, Any]:
    """Look up a single random meal and return its full recipe details."""
    data = _get("random.php")
    meals = data.get("meals")
    if not meals:
        return {"message": "no matches", "meal": None}
    return {"message": None, "meal": _full_details(meals[0])}


@mcp.tool()
def meal_details(id: str) -> dict[str, Any]:
    """Look up a single meal by id and return its full recipe details."""
    data = _get("lookup.php", {"i": id})
    meals = data.get("meals")
    if not meals:
        return {"message": "no matches", "meal": None}
    return {"message": None, "meal": _full_details(meals[0])}


if __name__ == "__main__":
    mcp.run(transport="stdio")
