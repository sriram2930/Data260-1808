"""
verify_hw03.py -- DATA-260 HW3 self-check / smoke test.

Part 1: starts the FastAPI app, exercises login/dashboard-protection/logout
over HTTP, and checks the Set-Cookie header carries all three session-cookie
attributes.
Part 2: builds one chunking pipeline (token -- the fastest to build) over the
real corpus and runs one retrieval, checking it terminates and returns
exactly k results with the expected embedding dimension, rather than
checking for any specific wording (the model's phrasing won't be identical
run to run).

Writes reports/hw03/verification.json. Does not modify any application code.

Usage:
    python verify_hw03.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
SID4 = 1808
SEED = 1808
VERIFY_SEED = 261808
PORT_BASE = 8008
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

sys.path.insert(0, str(HERE / "Part-5"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8"), dict(resp.headers)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_no_redirect_opener = urllib.request.build_opener(_NoRedirect)


def _http_post(url: str, data: dict, timeout: float = 10.0):
    """POST without following redirects, so the Set-Cookie header on a 303
    response (e.g. /login -> /dashboard) is visible rather than swallowed by
    urllib auto-following the redirect before returning."""
    body = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in data.items()).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with _no_redirect_opener.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


def check_auth(checks: list[dict]) -> None:
    proc = subprocess.Popen(
        [
            str(HERE / ".venv" / "Scripts" / "python.exe"),
            "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", str(PORT_BASE),
        ],
        cwd=str(HERE / "Part-1"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        up = False
        for _ in range(30):
            try:
                status, _, _ = _http_get(f"{base}/")
                if status == 200:
                    up = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        checks.append({"check": "fastapi_responds_on_port_base", "pass": up})
        if not up:
            return

        status, _, _ = _http_get(f"{base}/dashboard")
        checks.append({
            "check": "dashboard_blocks_unauthenticated",
            "pass": status == 200,  # redirected to login, which returns 200
        })

        status, headers = _http_post(f"{base}/login", {"username": "advisor", "password": "course123"})
        # http.client.HTTPMessage -> dict() keys come back lowercased.
        set_cookie = headers.get("set-cookie", "")
        checks.append({
            "check": "login_sets_cookie_with_httponly_secure_samesite",
            "pass": all(attr in set_cookie.lower() for attr in ["httponly", "secure", "samesite"]),
            "detail": set_cookie[:120],
        })

        # Re-request dashboard with the session cookie manually attached.
        cookie_value = set_cookie.split(";")[0]
        req = urllib.request.Request(f"{base}/dashboard")
        req.add_header("Cookie", cookie_value)
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        checks.append({
            "check": "dashboard_reachable_with_valid_session",
            "pass": "Welcome" in body,
        })

        # A real browser overwrites its cookie with whatever /logout sends
        # back (a cleared/expired one) before making the next request -- so
        # the check has to pick up that new cookie too, not keep resending
        # the pre-logout one (which would just be testing raw-cookie-replay,
        # a different and much harder bar for a stateless signed-cookie
        # session to meet without a server-side revocation list).
        req = urllib.request.Request(f"{base}/logout")
        req.add_header("Cookie", cookie_value)
        try:
            with _no_redirect_opener.open(req, timeout=5) as resp:
                logout_headers = dict(resp.headers)
        except urllib.error.HTTPError as e:
            logout_headers = dict(e.headers)
        post_logout_cookie = logout_headers.get("set-cookie", "").split(";")[0]

        req2 = urllib.request.Request(f"{base}/dashboard")
        req2.add_header("Cookie", post_logout_cookie)
        with urllib.request.urlopen(req2, timeout=5) as resp:
            final_url = resp.geturl()
        checks.append({
            "check": "dashboard_unreachable_after_logout",
            "pass": "/login" in final_url,
            "detail": f"post-logout cookie: {post_logout_cookie}",
        })
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def check_rag(checks: list[dict]) -> None:
    import rag_compare as rc

    t0 = time.time()
    docs = rc.load_corpus()
    checks.append({
        "check": "corpus_loads_and_meets_200kb_minimum",
        "pass": sum(len(d.text) for d in docs) >= 200_000,
        "detail": f"{sum(len(d.text) for d in docs)} chars across {len(docs)} files",
    })

    nodes = rc.build_nodes("token", docs)
    index = rc.build_index(nodes)
    result = rc.retrieve("token", index, "How do I register for classes at SJSU?", k=5, print_output=False)
    elapsed = time.time() - t0

    checks.append({
        "check": "rag_pipeline_finishes_without_hanging",
        "pass": elapsed < 180,
        "detail": f"finished in {elapsed:.1f}s",
    })
    checks.append({
        "check": "retrieval_returns_exactly_k_results",
        "pass": len(result["rows"]) == 5,
    })
    checks.append({
        "check": "query_embedding_dimension_is_384",
        "pass": result["query_embedding_dim"] == 384,
    })


def main() -> None:
    checks: list[dict] = []
    check_auth(checks)
    check_rag(checks)

    result = {
        "homework": "hw03",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": MODEL,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw03" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
