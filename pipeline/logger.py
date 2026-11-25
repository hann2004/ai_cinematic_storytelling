import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

RUNS_FILE = Path(__file__).resolve().parents[1] / "runs.jsonl"


def log_call(
    stage: str,
    model: str,
    params: Mapping[str, object],
    seed: int | str | None,
    latency_s: float,
    cost_estimate: float | None,
    status: str,
    note: str = "",
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "model": model,
        "params": dict(params),
        "seed": seed,
        "latency_s": latency_s,
        "cost_estimate": cost_estimate,
        "status": status,
        "note": note,
    }
    with RUNS_FILE.open("a", encoding="utf-8") as runs_file:
        runs_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def timed_call(
    stage: str,
    model: str,
    params: Mapping[str, object],
    seed: int | str | None,
    cost_estimate: float | None,
    function: Callable[..., T],
    *args: object,
    note: str = "",
    **kwargs: object,
) -> T:
    started = time.perf_counter()
    try:
        result = function(*args, **kwargs)
    except Exception as error:
        log_call(
            stage=stage,
            model=model,
            params=params,
            seed=seed,
            latency_s=time.perf_counter() - started,
            cost_estimate=cost_estimate,
            status="error",
            note=f"{note}; {type(error).__name__}".strip("; "),
        )
        raise

    log_call(
        stage=stage,
        model=model,
        params=params,
        seed=seed,
        latency_s=time.perf_counter() - started,
        cost_estimate=cost_estimate,
        status="success",
        note=note,
    )
    return result
