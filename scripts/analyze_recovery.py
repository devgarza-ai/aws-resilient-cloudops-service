#!/usr/bin/env python3
"""Recalculate recovery evidence without AWS access or external dependencies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


FIELDS = ("Sample", "ElapsedSeconds", "HttpStatus", "BackendRole", "RequestDurationMs", "ErrorCategory")


@dataclass(frozen=True)
class Observation:
    sample: int
    elapsed: Decimal
    status: int
    backend: str
    duration_ms: int
    error: str


def read_observations(data: bytes) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError("Unexpected CSV columns; use the normalized evidence schema.")
    rows: list[Observation] = []
    for expected_sample, raw in enumerate(reader, 1):
        if None in raw or any(v is None for v in raw.values()):
            raise ValueError(f"Incomplete CSV record at sample {expected_sample}.")
        try:
            row = Observation(int(raw["Sample"]), Decimal(raw["ElapsedSeconds"]),
                              int(raw["HttpStatus"]), raw["BackendRole"],
                              int(raw["RequestDurationMs"]), raw["ErrorCategory"])
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"Invalid numeric value at sample {expected_sample}.") from exc
        if row.sample != expected_sample:
            raise ValueError("Sample IDs must start at 1 and remain consecutive.")
        if not row.elapsed.is_finite() or row.elapsed < 0:
            raise ValueError("Elapsed starts must be finite and nonnegative.")
        if rows and row.elapsed <= rows[-1].elapsed:
            raise ValueError("Elapsed request starts must be strictly increasing.")
        if row.duration_ms < 0:
            raise ValueError("Request durations must be nonnegative.")
        if row.status != 0 and not 100 <= row.status <= 599:
            raise ValueError("Status must be 0 for no response or a valid HTTP status.")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", row.backend):
            raise ValueError("Backend roles must be neutral lowercase aliases.")
        if row.status == 200 and row.error:
            raise ValueError("HTTP 200 rows must not carry an error category.")
        if row.status != 200 and not row.error:
            raise ValueError("Non-200 rows must retain an error category.")
        rows.append(row)
    if not rows:
        raise ValueError("The CSV contains no observations.")
    if rows[0].elapsed != 0:
        raise ValueError("Normalize the first request start to zero elapsed seconds.")
    return rows


def seconds(value: Decimal | None) -> float | None:
    return None if value is None else float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def summarize(data: bytes) -> dict:
    rows = read_observations(data)
    successes = [r for r in rows if r.status == 200]
    error_indexes = [i for i, r in enumerate(rows) if r.status != 200]
    durations = sorted(r.duration_ms for r in successes)
    longest = run = 0
    for row in rows:
        run = run + 1 if row.status != 200 else 0
        longest = max(longest, run)
    first_error = rows[error_indexes[0]] if error_indexes else None
    last_error = rows[error_indexes[-1]] if error_indexes else None
    after = rows[error_indexes[-1] + 1:] if error_indexes else []
    first_after = next((r for r in after if r.status == 200), None)
    replacement = next((r for r in successes if r.backend == "replacement"), None)
    return {
        "schema": "project1-recovery-summary-v1",
        "evidence_sha256": hashlib.sha256(data).hexdigest(),
        "sample_count": len(rows),
        "http_status_counts": dict(sorted(Counter(str(r.status) for r in rows).items())),
        "http_200_count": len(successes),
        "sampled_http_200_percent": round(100 * len(successes) / len(rows), 2),
        "sampled_non_200_percent": round(100 * len(error_indexes) / len(rows), 2),
        "no_http_response_count": sum(r.status == 0 for r in rows),
        "observation_span_seconds": seconds(rows[-1].elapsed - rows[0].elapsed),
        "backend_http_200_counts": dict(sorted(Counter(r.backend for r in successes).items())),
        "successful_duration_ms": {
            "minimum": min(durations) if durations else None,
            "median": statistics.median(durations) if durations else None,
            "mean": round(statistics.mean(durations), 3) if durations else None,
            "p95_nearest_rank": durations[math.ceil(0.95 * len(durations)) - 1] if durations else None,
            "maximum": max(durations) if durations else None,
        },
        "error_observations": {
            "count": len(error_indexes),
            "first_elapsed_seconds": seconds(first_error.elapsed) if first_error else None,
            "last_elapsed_seconds": seconds(last_error.elapsed) if last_error else None,
            "first_to_last_span_seconds": seconds(last_error.elapsed - first_error.elapsed) if first_error else None,
            "interleaved_http_200_count": sum(r.status == 200 for r in rows[error_indexes[0]:error_indexes[-1] + 1]) if error_indexes else 0,
            "longest_consecutive_non_200": longest,
            "first_http_200_after_final_error_elapsed_seconds": seconds(first_after.elapsed) if first_after else None,
            "samples_after_final_error": len(after) if error_indexes else None,
            "all_samples_after_final_error_http_200": all(r.status == 200 for r in after) if after else None,
        },
        "first_replacement_http_200_elapsed_seconds": seconds(replacement.elapsed) if replacement else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--check", type=Path, help="Compare with a committed summary; fail on any difference.")
    args = parser.parse_args()
    try:
        result = summarize(args.csv_path.read_bytes())
        if args.check:
            expected = json.loads(args.check.read_text(encoding="utf-8"))
            if result != expected:
                print("FAIL: calculated summary differs from the committed evidence.", file=sys.stderr)
                return 1
            print("PASS: recovery evidence exactly matches the committed summary.")
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
