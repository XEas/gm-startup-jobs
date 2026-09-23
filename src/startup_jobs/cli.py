"""Command line entry point: `python -m startup_jobs <command>`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from startup_jobs.issue_form import IssueFormError, apply_issue
from startup_jobs.render import render_readme, render_to_file
from startup_jobs.validate import Report, validate_dir

ROOT = Path.cwd()


def _today(value: str | None) -> date:
    return date.fromisoformat(value) if value else datetime.now(timezone.utc).date()


def _print_report(report: Report) -> None:
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    for p in sorted(report.problems, key=lambda p: (p.level != "error", p.file)):
        print(p)
        if in_ci:
            print(f"::{p.level} file={p.file}::{p.message}")
    n = len(report.startups)
    print(
        f"\n{n} startup file(s) checked: {len(report.errors)} error(s), {len(report.warnings)} warning(s)."
    )


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_dir(args.data_dir, _today(args.today), root=ROOT)
    _print_report(report)
    return 0 if report.ok else 1


def _valid_startups(args: argparse.Namespace):
    report = validate_dir(args.data_dir, _today(args.today), root=ROOT)
    if not report.ok:
        _print_report(report)
        print("Not rendering: fix the errors above first.", file=sys.stderr)
        return None
    return report.startups.values()


def cmd_render(args: argparse.Namespace) -> int:
    startups = _valid_startups(args)
    if startups is None:
        return 1
    changed = render_to_file(startups, _today(args.today), args.templates_dir, args.output)
    print(f"{args.output} {'updated' if changed else 'already up to date'}.")
    return 0


def cmd_check_readme(args: argparse.Namespace) -> int:
    startups = _valid_startups(args)
    if startups is None:
        return 1
    header = (args.templates_dir / "header.md").read_text(encoding="utf-8")
    footer = (args.templates_dir / "footer.md").read_text(encoding="utf-8")
    expected = render_readme(startups, _today(args.today), header, footer)
    actual = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    if expected != actual:
        print(f"{args.output} is out of date. Run `make render`.", file=sys.stderr)
        return 1
    print(f"{args.output} is up to date.")
    return 0


def cmd_apply_issue(args: argparse.Namespace) -> int:
    body = args.body_file.read_text(encoding="utf-8")
    labels = [x for x in (args.labels or "").split(",") if x.strip()]
    today = _today(args.today)
    try:
        path, summary = apply_issue(body, args.data_dir, today, labels)
    except IssueFormError as exc:
        print("The issue form could not be processed:\n")
        for msg in exc.messages:
            print(f"- {msg}")
        return 1

    report = validate_dir(args.data_dir, today, root=ROOT)
    if not report.ok:
        print("The change was generated but failed validation:\n")
        for p in report.errors:
            print(f"- {p.file}: {p.message}")
        return 1

    print(summary)
    print(f"Wrote {path}")
    if args.summary_file:
        args.summary_file.write_text(summary + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="startup_jobs", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD); used by tests")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate every file in data/").set_defaults(func=cmd_validate)

    for name, func, help_ in (
        ("render", cmd_render, "regenerate README.md"),
        ("check-readme", cmd_check_readme, "fail if README.md is out of date"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--templates-dir", type=Path, default=Path("templates"))
        p.add_argument("--output", type=Path, default=Path("README.md"))
        p.set_defaults(func=func)

    p = sub.add_parser("apply-issue", help="apply a GitHub issue-form body to data/")
    p.add_argument("--body-file", type=Path, required=True)
    p.add_argument("--labels", help="comma-separated issue labels, used to detect the form type")
    p.add_argument("--summary-file", type=Path, help="write a one-line summary here on success")
    p.set_defaults(func=cmd_apply_issue)

    args = parser.parse_args(argv)
    return args.func(args)
