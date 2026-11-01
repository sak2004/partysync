#!/usr/bin/env python3
"""Single source of truth for PartySync progress.

docs/status.json  ->  the status tables inside README.md (between the markers).

  python scripts/status.py show
  python scripts/status.py set M1 in-progress --note "ring buffer written"
  python scripts/status.py set M1 done --tag      # also creates git tag milestone-M1
  python scripts/status.py hw H3 pass --note "Flip 7 + Charge 4, 30 min, no dropouts"
  python scripts/status.py render                 # rewrite the README tables
  python scripts/status.py check                  # exit 1 if README is out of date

Only the standard library is used, so this works before anything is installed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "docs" / "status.json"
README = ROOT / "README.md"
START = "<!-- STATUS:START -->"
END = "<!-- STATUS:END -->"

MILESTONE_STATES = {
    "todo": "TODO",
    "in-progress": "IN PROGRESS",
    "needs-hw-test": "NEEDS HW TEST",
    "done": "DONE",
    "blocked": "BLOCKED",
}
HW_STATES = {"todo": "TODO", "pass": "PASS", "fail": "FAIL"}


def _load() -> dict:
    with open(STATUS, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(STATUS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _cell(text: object) -> str:
    cleaned = str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()
    return cleaned or "-"


def render_block(data: dict) -> str:
    milestones, checks = data["milestones"], data["hardware_checks"]
    done = sum(m["state"] == "done" for m in milestones)
    passed = sum(h["state"] == "pass" for h in checks)
    lines = [
        f"**Progress:** {done} of {len(milestones)} milestones done, "
        f"{passed} of {len(checks)} hardware checks passed (last update {data['updated']}).",
        "",
        "### Milestones",
        "",
        "| ID | Milestone | Status | What is expected | Notes |",
        "|----|-----------|--------|------------------|-------|",
    ]
    for m in milestones:
        lines.append(
            f"| {m['id']} | {_cell(m['title'])} | **{MILESTONE_STATES[m['state']]}** "
            f"| {_cell(m['expected'])} | {_cell(m.get('note', ''))} |"
        )
    lines += [
        "",
        "### Hardware checks (only you can run these on the real speakers)",
        "",
        "| ID | Check | Status | Notes |",
        "|----|-------|--------|-------|",
    ]
    for h in checks:
        lines.append(
            f"| {h['id']} | {_cell(h['check'])} | **{HW_STATES[h['state']]}** | {_cell(h.get('note', ''))} |"
        )
    return "\n".join(lines)


def render_readme(text: str, data: dict) -> str:
    try:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
    except ValueError:
        raise SystemExit(f"README.md must contain {START} and {END} markers.")
    return f"{head}{START}\n{render_block(data)}\n{END}{tail}"


def _read_readme() -> str:
    with open(README, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def _write_readme(text: str) -> None:
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _find(items: list[dict], item_id: str, kind: str) -> dict:
    for item in items:
        if item["id"].lower() == item_id.lower():
            return item
    known = ", ".join(i["id"] for i in items)
    raise SystemExit(f"Unknown {kind} id '{item_id}'. Known ids: {known}")


def cmd_show(_args: argparse.Namespace) -> int:
    data = _load()
    print(f"{data['project']} (last update {data['updated']})")
    for m in data["milestones"]:
        print(f"  {m['id']:<3} {MILESTONE_STATES[m['state']]:<14} {m['title']}")
    print("Hardware checks")
    for h in data["hardware_checks"]:
        print(f"  {h['id']:<3} {HW_STATES[h['state']]:<14} {h['check']}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    data = _load()
    item = _find(data["milestones"], args.id, "milestone")
    item["state"] = args.state
    if args.note is not None:
        item["note"] = args.note
    data["updated"] = dt.date.today().isoformat()
    _save(data)
    _write_readme(render_readme(_read_readme(), data))
    print(f"{item['id']} -> {MILESTONE_STATES[args.state]}")
    if args.tag:
        if args.state != "done":
            print("--tag is only used with state 'done'; no tag created.", file=sys.stderr)
        else:
            result = subprocess.run(
                ["git", "tag", "-a", f"milestone-{item['id']}", "-m", f"{item['id']} {item['title']}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"Created git tag milestone-{item['id']}")
            else:
                print(f"Could not create tag: {result.stderr.strip()}", file=sys.stderr)
    return 0


def cmd_hw(args: argparse.Namespace) -> int:
    data = _load()
    item = _find(data["hardware_checks"], args.id, "hardware check")
    item["state"] = args.state
    if args.note is not None:
        item["note"] = args.note
    data["updated"] = dt.date.today().isoformat()
    _save(data)
    _write_readme(render_readme(_read_readme(), data))
    print(f"{item['id']} -> {HW_STATES[args.state]}")
    return 0


def cmd_render(_args: argparse.Namespace) -> int:
    _write_readme(render_readme(_read_readme(), _load()))
    print("README.md status tables updated.")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    expected = render_readme(_read_readme(), _load())
    if expected != _read_readme():
        print("README.md status tables are out of date. Run: python scripts/status.py render", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PartySync progress tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="print current status").set_defaults(func=cmd_show)

    p_set = sub.add_parser("set", help="change a milestone's status")
    p_set.add_argument("id")
    p_set.add_argument("state", choices=sorted(MILESTONE_STATES))
    p_set.add_argument("--note")
    p_set.add_argument("--tag", action="store_true", help="create git tag milestone-<id> (state done only)")
    p_set.set_defaults(func=cmd_set)

    p_hw = sub.add_parser("hw", help="record a hardware check result")
    p_hw.add_argument("id")
    p_hw.add_argument("state", choices=sorted(HW_STATES))
    p_hw.add_argument("--note")
    p_hw.set_defaults(func=cmd_hw)

    sub.add_parser("render", help="rewrite README tables from docs/status.json").set_defaults(func=cmd_render)
    sub.add_parser("check", help="exit 1 if README tables are stale").set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
