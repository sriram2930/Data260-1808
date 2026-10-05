"""
Part-7/retry_policy.py -- DATA-260 HW5, Part 3 (timeouts + bounded
exponential-backoff retry)

call_with_retry wraps any zero-argument callable with:
  - a per-attempt timeout (enforced with a worker thread, since a plain
    synchronous Python call can't be preemptively interrupted otherwise --
    the call still returns promptly to the caller even if a stuck worker
    thread lingers in the background, which is the standard, documented
    trade-off of this approach)
  - a bounded number of retries (max_retries+1 total attempts)
  - exponential backoff between attempts (base_delay_s * 2**attempt_index)

On total failure it raises RetryExhausted instead of the original
exception, so a caller gets one clean, predictable error instead of
crashing on whatever the underlying operation happened to throw.

FlakyOperation / CountingFlakyOperation simulate operations that fail, for
Part 3.19's demonstration and Part 3.20's 150-call fault-injection
experiment (run_fault_injection.py).
"""

from __future__ import annotations

import concurrent.futures
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


class RetryExhausted(Exception):
    """Raised when every attempt (including retries) failed or timed out."""


@dataclass
class AttemptLog:
    attempt: int
    success: bool
    elapsed_ms: float
    error: Optional[str]


def call_with_retry(
    fn: Callable[[], object],
    *,
    max_retries: int = 2,
    base_delay_s: float = 0.02,
    timeout_s: float = 1.0,
) -> tuple[object, list[AttemptLog]]:
    """Returns (result, attempt_log) on success. Raises RetryExhausted (with
    attempt_log attached as .attempts) if every attempt fails or times out."""
    attempts: list[AttemptLog] = []
    last_exc: Optional[BaseException] = None

    for attempt in range(max_retries + 1):
        t0 = time.perf_counter()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(fn)
                result = future.result(timeout=timeout_s)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            attempts.append(AttemptLog(attempt, True, elapsed_ms, None))
            return result, attempts
        except Exception as exc:  # noqa: BLE001 -- intentionally broad: any
            # failure mode (simulated error, real timeout, real exception)
            # goes through the same retry/backoff path.
            elapsed_ms = (time.perf_counter() - t0) * 1000
            last_exc = exc
            attempts.append(AttemptLog(attempt, False, elapsed_ms, str(exc)))
            if attempt < max_retries:
                time.sleep(base_delay_s * (2 ** attempt))

    exc = RetryExhausted(f"all {max_retries + 1} attempts failed: {last_exc}")
    exc.attempts = attempts  # type: ignore[attr-defined]
    raise exc


@dataclass
class FlakyOperation:
    """A simulated operation that fails at a fixed rate, reproducible from a
    seed: one random.Random(seed) stream is consumed one draw per attempt,
    in call order, so re-running the same seed against the same call
    sequence always reproduces the same success/failure pattern."""

    seed: int
    failure_rate: float
    latency_ms: float = 40.0
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def __call__(self) -> str:
        time.sleep(self.latency_ms / 1000)
        if self._rng.random() < self.failure_rate:
            raise RuntimeError("simulated failure")
        return "ok"


@dataclass
class CountingFlakyOperation:
    """A deterministic (non-random) flaky operation for Part 3.19's
    demonstration: fails on the first `fail_first_n` calls, then succeeds.
    Used instead of seed-hunting a random example for each of the three
    required demo scenarios."""

    fail_first_n: int
    latency_ms: float = 40.0
    _calls: int = field(default=0, init=False)

    def __call__(self) -> str:
        self._calls += 1
        time.sleep(self.latency_ms / 1000)
        if self._calls <= self.fail_first_n:
            raise RuntimeError(f"simulated failure (attempt {self._calls})")
        return "ok"
