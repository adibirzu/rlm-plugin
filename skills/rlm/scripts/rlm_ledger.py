#!/usr/bin/env python3
"""Validate an RLM worker result or evidence ledger before it is synthesized.

Accepts the Markdown worker format from SKILL.md or the equivalent JSON object.
Checks that Coverage, Findings, Counterevidence, and Verification are present
and filled in, that every finding cites path:line or a URL, and that the
recursion depth stays inside the declared budget and the model-tier ceiling.
With --root, cited files and line numbers must exist under that directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

# Single owner of the model-tier recursion budgets. The table in SKILL.md is
# checked against this mapping by the test suite.
TIER_BUDGETS = {
    "frontier": {"default_depth": 1, "max_depth": 2, "max_fanout": 8, "max_subcalls": 16},
    "mid": {"default_depth": 1, "max_depth": 1, "max_fanout": 5, "max_subcalls": 8},
    "small": {"default_depth": 0, "max_depth": 1, "max_fanout": 3, "max_subcalls": 4},
}
DEPTH_NEEDING_DEPENDENCY = 2
REQUIRED_SECTIONS = ("coverage", "findings", "counterevidence", "verification")

PLACEHOLDER_WORDS = frozenset({"", "tbd", "todo", "n/a", "na", "...", "-", "?", "unknown", "pending"})
ABSENT_WORDS = PLACEHOLDER_WORDS | {"none", "no", "false", "null"}
NO_FINDINGS = re.compile(r"(none|no (confirmed )?findings?)( (found|identified|confirmed))?[.!]?", re.I)
TEMPLATE_SLOT = re.compile(r"<[^<>]*>")
PLACEHOLDER_CITATIONS = frozenset({"path:line", "file:line", "path:line-line", "url"})
PLACEHOLDER_HOSTS = re.compile(r"(^|\.)(example\.(com|org|net)|localhost)$", re.I)
PATH_LINE = re.compile(
    r"^(?P<path>[^:\s][^:]*):(?P<start>\d{1,9})(?::\d{1,9})?(?:-(?P<end>\d{1,9}))?$"
)
BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(?P<text>.*)$")
KEY_VALUE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z _-]*):\s*(?P<value>.*)$")

EPILOG = """\
Examples:
  rlm_ledger.py .rlm/audit/worker-03.md --root . --tier mid
  rlm_ledger.py ledger.json --json

Exit codes:
  0  the ledger is valid
  1  the ledger has errors (listed on standard output)
  2  usage error, or the input could not be read or parsed
"""


class LedgerInputError(Exception):
    """The input cannot be read as a ledger at all."""


@dataclass
class Finding:
    title: str
    citations: list[str] = field(default_factory=list)


@dataclass
class Ledger:
    present: set[str] = field(default_factory=set)
    reviewed: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    declares_no_findings: bool = False
    counterevidence: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    budget: dict[str, object] = field(default_factory=dict)


@dataclass
class Issue:
    code: str
    where: str
    message: str


def normalize_key(key: object) -> str:
    return re.sub(r"[\s-]+", "_", str(key).strip().lower())


def as_text_list(value: object) -> list[str]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    if isinstance(value, dict):
        return [" ".join(str(item) for item in value.values())]
    return [text for item in value for text in as_text_list(item)]


def parse_json(text: str) -> Ledger:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise LedgerInputError(f"not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise LedgerInputError("the JSON ledger must be an object")
    data = {normalize_key(key): value for key, value in raw.items()}

    ledger = Ledger(present={name for name in REQUIRED_SECTIONS if name in data})
    coverage = data.get("coverage")
    if isinstance(coverage, dict):
        coverage = {normalize_key(k): v for k, v in coverage.items()}.get("reviewed")
    ledger.reviewed = as_text_list(coverage)

    findings = data.get("findings")
    if isinstance(findings, list):
        ledger.declares_no_findings = not findings
        for item in findings:
            if isinstance(item, dict):
                item = {normalize_key(k): v for k, v in item.items()}
                location = item.get("location")
                citations = (
                    [clean_citation(str(entry)) for entry in location]
                    if isinstance(location, list)
                    else split_citations(str(location or ""))
                )
                ledger.findings.append(Finding(str(item.get("title", "")), citations))
            else:
                ledger.findings.append(Finding(str(item)))

    ledger.counterevidence = as_text_list(data.get("counterevidence"))
    ledger.verification = as_text_list(data.get("verification"))
    budget = data.get("budget")
    if isinstance(budget, dict):
        ledger.budget = {normalize_key(k): v for k, v in budget.items()}
    return ledger


def parse_markdown(text: str) -> Ledger:
    ledger = Ledger()
    section = None
    finding: Finding | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = normalize_key(line[3:].strip().rstrip(":"))
            finding = None
            if section in REQUIRED_SECTIONS:
                ledger.present.add(section)
            continue
        if section == "findings" and line.startswith("### "):
            finding = Finding(line[4:].strip())
            ledger.findings.append(finding)
            continue

        bullet = BULLET.match(line)
        entry = (bullet.group("text") if bullet else line).strip()
        if not entry:
            continue
        pair = KEY_VALUE.match(entry)
        key = normalize_key(pair.group("key")) if pair else None
        value = pair.group("value").strip() if pair else None

        if section == "budget" and pair:
            ledger.budget[key] = value
        elif section == "coverage" and key == "reviewed":
            ledger.reviewed += [part.strip() for part in value.split(",")]
        elif section == "findings":
            if finding is None:
                ledger.declares_no_findings |= bool(NO_FINDINGS.fullmatch(entry.strip("`*_ ")))
            elif key == "location":
                finding.citations = split_citations(value)
        elif section == "counterevidence":
            ledger.counterevidence.append(entry)
        elif section == "verification":
            ledger.verification.append(entry)
    return ledger


def is_placeholder(text: str, words: frozenset[str] = PLACEHOLDER_WORDS) -> bool:
    cleaned = text.strip().strip("`*_ ").lower()
    return cleaned in words or bool(TEMPLATE_SLOT.fullmatch(cleaned))


def count_lines(path: Path) -> int:
    lines = 0
    last = b"\n"
    with path.open("rb") as handle:
        while block := handle.read(1 << 16):
            lines += block.count(b"\n")
            last = block[-1:]
    return lines + (last != b"\n")


def check_citation(token: str, root: Path | None) -> tuple[str, str] | None:
    """Return (code, message) for a bad citation, or None when it is acceptable."""
    lowered = token.lower()
    if is_placeholder(token, ABSENT_WORDS) or TEMPLATE_SLOT.search(token) or lowered in PLACEHOLDER_CITATIONS:
        return "placeholder-citation", f"'{token}' is a template placeholder, not evidence"

    if lowered.startswith(("http://", "https://")):
        try:
            parsed = urlparse(token)
            host = parsed.hostname or ""
            parsed.port  # raises ValueError for a malformed port
        except ValueError:
            host = ""
        if PLACEHOLDER_HOSTS.search(host):
            return "placeholder-citation", f"'{token}' points at a placeholder host"
        if not re.search(r"[.:]", host) or re.search(r"\s", token):
            return "bad-citation", f"'{token}' is not a well-formed URL"
        return None

    match = PATH_LINE.match(token)
    start = int(match.group("start")) if match else 0
    end = int(match.group("end") or start) if match else 0
    if not match or start < 1 or end < start:
        return "bad-citation", f"'{token}' must be path:line, path:start-end, or an http(s) URL"
    if root is None:
        return None

    cited = Path(match.group("path"))
    try:
        resolved = (cited if cited.is_absolute() else root / cited).resolve()
        if not resolved.is_relative_to(root):
            return "citation-outside-root", f"'{token}' resolves outside {root}"
        if not resolved.is_file():
            return "fabricated-citation", f"'{match.group('path')}' does not exist under {root}"
        total = count_lines(resolved)
    except ValueError:
        return "bad-citation", "the cited path is not a valid file name"
    except (OSError, RuntimeError) as error:
        return "fabricated-citation", f"'{match.group('path')}' cannot be read: {error}"
    if end > total:
        return "fabricated-citation", f"'{token}' cites line {end} but the file has {total} lines"
    return None


def clean_citation(text: str) -> str:
    return text.replace("`", "").strip()


def split_citations(location: str) -> list[str]:
    """Split on a comma or semicolon followed by a space, so URLs stay whole."""
    return [part for part in re.split(r"[,;]\s+", clean_citation(location)) if part]


def to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip()
    return int(text) if text.isascii() and text.isdigit() and len(text) <= 9 else None


def check_budget(budget: dict[str, object]) -> list[Issue]:
    issues = []
    tier = budget.get("tier")
    cap = max(entry["max_depth"] for entry in TIER_BUDGETS.values())
    if tier is not None:
        tier = str(tier).strip().lower()
        if tier in TIER_BUDGETS:
            cap = TIER_BUDGETS[tier]["max_depth"]
        else:
            known = ", ".join(TIER_BUDGETS)
            issues.append(Issue("unknown-tier", "budget.tier", f"'{tier}' is not one of: {known}"))

    numbers = {}
    for name in ("depth", "max_depth"):
        raw = budget.get(name)
        numbers[name] = None if raw is None else to_int(raw)
        if raw is not None and numbers[name] is None:
            issues.append(Issue("bad-budget", f"budget.{name}", f"'{raw}' is not a non-negative integer"))
    depth = numbers["depth"] or 0
    max_depth = numbers["max_depth"]

    for name, value in (("depth", depth), ("max_depth", max_depth or 0)):
        if value > cap:
            scope = f"the {tier} tier" if tier in TIER_BUDGETS else "any tier"
            issues.append(Issue("depth-over-tier", f"budget.{name}", f"{name} {value} exceeds the ceiling of {cap} for {scope}"))

    deep = depth >= DEPTH_NEEDING_DEPENDENCY
    dependency = budget.get("named_dependency")
    if deep and (dependency is None or is_placeholder(str(dependency), ABSENT_WORDS)):
        issues.append(Issue("depth-without-dependency", "budget.named_dependency", f"depth {depth} needs a named unresolved dependency"))
    if (deep and max_depth is None) or (max_depth is not None and depth > max_depth):
        issues.append(Issue("depth-unbudgeted", "budget.max_depth", f"depth {depth} is not covered by a declared max_depth"))
    return issues


def validate(ledger: Ledger, root: Path | None) -> tuple[list[Issue], int]:
    issues = [
        Issue("missing-section", name, f"the {name.capitalize()} section is required")
        for name in REQUIRED_SECTIONS
        if name not in ledger.present
    ]

    def require_content(name: str, entries: list[str], hint: str) -> None:
        if name in ledger.present and all(is_placeholder(entry) for entry in entries):
            issues.append(Issue("empty-section", name, hint))

    require_content("coverage", ledger.reviewed, "list what was reviewed")
    require_content("counterevidence", ledger.counterevidence, "state the counterevidence, or 'none found' with the search that was run")
    require_content("verification", ledger.verification, "state the check that was run, or why none could run")
    if "findings" in ledger.present and not ledger.findings and not ledger.declares_no_findings:
        issues.append(Issue("empty-section", "findings", "add findings, or state 'None' explicitly"))

    citations = 0
    for index, finding in enumerate(ledger.findings):
        where = f"findings[{index}]"
        tokens = [token for token in finding.citations if token]
        if not tokens:
            issues.append(Issue("empty-citation", where, f"'{finding.title}' has no Location"))
        for token in tokens:
            citations += 1
            problem = check_citation(token, root)
            if problem:
                issues.append(Issue(problem[0], where, problem[1]))

    return issues + check_budget(ledger.budget), citations


def read_ledger(source: str, declared_format: str) -> Ledger:
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text()
    except (OSError, UnicodeDecodeError) as error:
        raise LedgerInputError(f"cannot read {source}: {error}") from error
    chosen = declared_format
    if chosen == "auto":
        chosen = "json" if source.endswith(".json") or text.lstrip().startswith("{") else "markdown"
    return parse_json(text) if chosen == "json" else parse_markdown(text)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("ledger", help="ledger file, or - for standard input")
    parser.add_argument("--format", choices=("auto", "json", "markdown"), default="auto")
    parser.add_argument("--root", type=Path, help="check cited paths and lines under this directory")
    parser.add_argument("--tier", choices=tuple(TIER_BUDGETS), help="tier the coordinator dispatched (overrides the ledger)")
    parser.add_argument("--depth", type=int, help="depth the coordinator dispatched (overrides the ledger)")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = None
    if args.root is not None:
        if not args.root.is_dir():
            print(f"error: --root {args.root} is not a directory", file=sys.stderr)
            return 2
        root = args.root.resolve()
    try:
        ledger = read_ledger(args.ledger, args.format)
    except LedgerInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.tier is not None:
        ledger.budget["tier"] = args.tier
    if args.depth is not None:
        ledger.budget["depth"] = args.depth

    issues, citations = validate(ledger, root)
    summary = {"findings": len(ledger.findings), "citations": citations}
    if args.json:
        report = {"valid": not issues, "errors": [vars(issue) for issue in issues], "summary": summary}
        print(json.dumps(report, indent=1))
    elif issues:
        print(f"INVALID: {len(issues)} error(s)")
        for issue in issues:
            print(f"- {issue.code} [{issue.where}]: {issue.message}")
    else:
        print(f"OK: {summary['findings']} finding(s), {summary['citations']} citation(s) checked")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
