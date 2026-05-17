"""Probe fetch strategies for one or more URLs.

This is the Python-native replacement for the old JavaScript probe path. It tries
the same strategy families the pipeline fetcher uses, reports the first working
strategy, and can update the shared host strategy map.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .fetch_client import FetchClient, looks_blocked, probe_attempts
from .settings import DEFAULT_USER_AGENT, HOST_STRATEGIES_PATH
from .utils import load_json, write_json


def probe_url(url: str, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    client = FetchClient(
        user_agent=DEFAULT_USER_AGENT,
        per_host_delay_seconds=0.0,
        timeout_seconds=timeout_seconds,
    )
    failures: list[dict[str, Any]] = []
    tested_at = datetime.now(timezone.utc).date().isoformat()

    for attempt in probe_attempts(url):
        try:
            result = client.fetch_once(attempt)
        except Exception as exc:  # noqa: BLE001 - diagnostics should keep trying strategies
            failures.append({"strategy": attempt.strategy, "error": f"{type(exc).__name__}: {exc}"})
            continue

        blocked = looks_blocked(result)
        failures.append({"strategy": attempt.strategy, "status": result.status, "bytes": len(result.body), "blocked": blocked})
        if 200 <= result.status < 400 and not blocked and result.body:
            return {
                "strategy": attempt.strategy,
                "kind": attempt.source,
                "status": result.status,
                "bytes": len(result.body),
                "sample_url": url,
                "tested_at": tested_at,
                "final_url": result.final_url,
                "failures": failures[:-1],
            }

    return {
        "strategy": None,
        "kind": None,
        "status": None,
        "bytes": None,
        "sample_url": url,
        "tested_at": tested_at,
        "note": "all strategies failed or were blocked",
        "failures": failures,
    }


def _load_strategy_map(path: Path) -> dict[str, Any]:
    value = load_json(path, {})
    return value if isinstance(value, dict) else {}


def _write_strategy_map(path: Path, values: dict[str, Any]) -> None:
    write_json(path, values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Python fetch strategies for URL(s).")
    parser.add_argument("urls", nargs="+", help="URL(s) to probe")
    parser.add_argument("--write", action="store_true", help="Update the host strategy map with probe results")
    parser.add_argument("--strategy-map", type=Path, default=HOST_STRATEGIES_PATH)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    results = [probe_url(url, timeout_seconds=args.timeout) for url in args.urls]

    if args.write:
        strategy_map = _load_strategy_map(args.strategy_map)
        for result in results:
            host = urlparse(result["sample_url"]).netloc.lower()
            if host:
                strategy_map[host] = {key: value for key, value in result.items() if key != "failures"}
        _write_strategy_map(args.strategy_map, strategy_map)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()