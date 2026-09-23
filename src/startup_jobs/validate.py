"""Schema and cross-file checks over the whole data/ directory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from startup_jobs.loader import Problem, load_startup
from startup_jobs.models import Startup
from startup_jobs.slug import is_kebab, slugify

STALE_AFTER_DAYS = 60
ROLE_MAILBOXES = {
    "jobs", "careers", "career", "hiring", "recruiting", "recruit", "recruiter", "talent",
    "internships", "internship", "interns", "people", "hr", "team", "hello", "apply", "work",
}


@dataclass
class Report:
    startups: dict[str, Startup] = field(default_factory=dict)  # display path -> startup
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, file: str, message: str) -> None:
        self.problems.append(Problem("error", file, message))

    def warn(self, file: str, message: str) -> None:
        self.problems.append(Problem("warning", file, message))


def is_stale(confirmed: date, today: date) -> bool:
    return confirmed < today - timedelta(days=STALE_AFTER_DAYS)


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def _normalize_url(url: str) -> str:
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}?{p.query}".rstrip("?")


def data_files(data_dir: Path) -> list[Path]:
    return sorted(p for p in data_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def validate_dir(data_dir: Path, today: date, root: Path | None = None) -> Report:
    report = Report()
    root = root or data_dir.parent

    for path in data_files(data_dir):
        display = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        if path.suffix != ".yaml":
            report.error(display, "data files must use the .yaml extension")
            continue
        startup, problems = load_startup(path, display)
        report.problems.extend(problems)
        if startup is not None:
            report.startups[display] = startup

    _check_files(report, today)
    return report


def _check_files(report: Report, today: date) -> None:
    by_slug: dict[str, str] = {}
    by_domain: dict[str, str] = {}
    by_role_url: dict[str, str] = {}

    for file, s in report.startups.items():
        stem = Path(file).stem
        expected = slugify(s.name)
        if not is_kebab(stem) or stem != expected:
            report.error(file, f"filename must be {expected}.yaml to match name {s.name!r}")

        if expected in by_slug:
            report.error(file, f"startup {s.name!r} is already listed in {by_slug[expected]}")
        by_slug.setdefault(expected, file)

        domain = _domain(s.website)
        if domain in by_domain:
            report.error(file, f"website {domain} is already used by {by_domain[domain]}")
        by_domain.setdefault(domain, file)

        seen_identity: dict[tuple, int] = {}
        for i, role in enumerate(s.roles):
            where = f"roles[{i}]"
            if role.identity in seen_identity:
                report.error(
                    file,
                    f"{where}: duplicate role (same title, level and term as roles[{seen_identity[role.identity]}])",
                )
            seen_identity.setdefault(role.identity, i)

            if role.url:
                key = _normalize_url(role.url)
                if key in by_role_url:
                    report.error(file, f"{where}.url: {role.url} is already used by {by_role_url[key]}")
                by_role_url.setdefault(key, f"{file} {where}")

            if role.confirmed > today:
                report.error(file, f"{where}.confirmed: {role.confirmed} is in the future")
            elif role.status == "open" and is_stale(role.confirmed, today):
                age = (today - role.confirmed).days
                report.warn(
                    file,
                    f"{where}.confirmed: {role.title!r} was last confirmed {age} days ago; "
                    "re-confirm it or mark it closed",
                )

            if role.contact and role.contact.split("@")[0] not in ROLE_MAILBOXES:
                report.warn(
                    file,
                    f"{where}.contact: {role.contact} looks like a personal address; "
                    "prefer a role address such as jobs@ or careers@",
                )
