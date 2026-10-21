#!/usr/bin/env python3
"""Check public documentation links, evidence consistency, and configuration boundaries."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from analyze_recovery import summarize


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def slug(value: str) -> str:
    return re.sub(r"[^\w -]", "", value.lower().replace("`", "")).replace(" ", "-")


def validate() -> int:
    errors: list[str] = []
    files = [p for p in ROOT.rglob("*") if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in (".git", "__pycache__"))]
    required = ("README.md", "LICENSE", "assets/architecture.svg", "assets/recovery-results.svg",
                "docs/incidents/recovery-incident.md", "evidence/recovery-observations.csv",
                "evidence/recovery-summary.json", "evidence/audit-event.json",
                "evidence/config-evaluations.json", "scripts/bootstrap.sh")
    for item in required:
        if not (ROOT / item).is_file():
            errors.append(f"Required artifact missing: {item}")

    for path in files:
        rel = path.relative_to(ROOT)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Unexpected binary public artifact: {rel}")
            continue
        if path.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as exc:
                errors.append(f"Invalid JSON in {rel}: {exc}")
        if path.suffix == ".svg":
            try:
                ET.fromstring(text)
            except ET.ParseError as exc:
                errors.append(f"Invalid SVG in {rel}: {exc}")
        if re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", text):
            errors.append(f"Credential identifier in {rel}")
        if re.search(r"\b\d{12}\b", text):
            errors.append(f"Unredacted account-like identifier in {rel}")
        if re.search(r"https?://dg-p1-alb-[^\s/'\"]+", text):
            errors.append(f"Account-specific ALB endpoint in {rel}")
        if path.suffix == ".md":
            if re.search(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b|\b20\d{2}-\d{2}-\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d", text):
                errors.append(f"Calendar metadata in public documentation: {rel}")
            if re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|UTC|PDT|PST)\b", text):
                errors.append(f"Wall-clock value in public documentation: {rel}")
            if re.search(r"\b(?:cleanup|teardown)\b", text, re.I):
                errors.append(f"Out-of-scope operational checklist in {rel}")
            for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
                target = target.split(' "', 1)[0]
                if re.match(r"(?:[a-z]+:|//)", target):
                    continue
                dest, _, fragment = target.partition("#")
                resolved = (path.parent / unquote(dest)).resolve() if dest else path
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    errors.append(f"Broken local link in {rel}: {target}")
                    continue
                if fragment and resolved.suffix == ".md":
                    heads = {slug(h) for h in re.findall(r"^#{1,6}\s+(.+)$", resolved.read_text(), re.M)}
                    if fragment not in heads:
                        errors.append(f"Missing heading anchor in {rel}: {target}")

    try:
        actual = summarize((ROOT / "evidence/recovery-observations.csv").read_bytes())
        expected = json.loads((ROOT / "evidence/recovery-summary.json").read_text())
        require(actual == expected, "Recovery summary does not match the CSV.")
        require(actual["sample_count"] == 265 and actual["http_status_counts"] == {"200": 259, "502": 6}, "Published recovery result changed.")
        require(actual["error_observations"]["samples_after_final_error"] == 204, "Successful tail count changed.")
        require(actual["error_observations"]["all_samples_after_final_error_http_200"] is True, "Successful tail no longer holds.")
        agent = json.loads((ROOT / "config/cloudwatch-agent.json").read_text())
        require(agent["agent"]["region"] == "us-east-1", "Agent Region changed.")
        logs = agent["logs"]["logs_collected"]["files"]["collect_list"]
        require(len(logs) == 3 and all(r["log_stream_name"] == "{instance_id}" for r in logs), "Agent log paths/stream strategy changed.")
        policy = json.loads((ROOT / "iam/cloudwatch-logs-policy.template.json").read_text())
        resources = policy["Statement"][1]["Resource"]
        require(len(resources) == 3 and all(":ACCOUNT_ID:log-group:/devgarza/project1/" in r for r in resources), "Logging policy must retain its public account placeholder and bounded groups.")
        audit = json.loads((ROOT / "evidence/audit-event.json").read_text())
        require(audit["event_name"] == "CreateTags" and audit["success"] is True and audit["source_record_count"] == 42, "Audit evidence changed.")
        config = json.loads((ROOT / "evidence/config-evaluations.json").read_text())
        counts = {r["name"]: r["compliant_resource_count"] for r in config["rules"]}
        require(counts == {"restricted-ssh": 4, "encrypted-volumes": 2}, "Config evidence changed.")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(files)} public files; local links, JSON/SVG, evidence, and identifier checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
