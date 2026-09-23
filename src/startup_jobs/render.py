"""Render every startup into README.md. README.md is never edited by hand."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from startup_jobs.models import Role, Startup
from startup_jobs.validate import STALE_AFTER_DAYS, is_stale

GENERATED_NOTICE = (
    "<!-- This file is generated from data/*.yaml by `make render`. "
    "Do not edit it by hand; your changes will be overwritten. -->"
)

STAGE_LABELS = {
    "pre-seed": "Pre-seed",
    "seed": "Seed",
    "series-a": "Series A",
    "series-b": "Series B",
    "series-c+": "Series C+",
    "bootstrapped": "Bootstrapped",
    "unknown": "—",
}
LEVEL_SECTIONS = (("intern", "Internships"), ("new-grad", "New Grad"))
COLUMNS = ("Company", "What they do", "Stage", "Role", "Location", "Apply", "Confirmed")


def cell(text: str) -> str:
    """Make arbitrary text safe inside a Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def link(text: str, url: str) -> str:
    return f"[{cell(text).replace('[', '(').replace(']', ')')}]({url.replace(' ', '%20').replace(')', '%29')})"


def company_cell(s: Startup) -> str:
    out = f"**{link(s.name, s.website)}**"
    if s.affiliations:
        out += "<br><sub>" + cell(", ".join(s.affiliations)) + "</sub>"
    return out


def role_cell(r: Role) -> str:
    details = " · ".join(x for x in (r.term, r.category, "closed" if r.status == "closed" else None) if x)
    return f"{cell(r.title)}<br><sub>{cell(details)}</sub>"


def location_cell(s: Startup) -> str:
    out = cell("; ".join(s.locations))
    if s.remote_ok and not any(loc.lower() == "remote" for loc in s.locations):
        out += " (remote ok)"
    return out


def what_cell(s: Startup) -> str:
    out = cell(s.one_liner)
    if s.notes:
        out += f"<br><sub>{cell(s.notes)}</sub>"
    return out


def apply_cell(r: Role) -> str:
    if r.status == "closed":
        return "Closed"
    out = link("Email", r.apply_link) if r.apply_method == "email" else link("Apply", r.apply_link)
    if r.apply_tips:
        out += f"<br><sub>{cell(r.apply_tips)}</sub>"
    return out


def row(s: Startup, r: Role, repeat: bool = False) -> str:
    """One table row. `repeat` rows continue the previous company, so its details aren't shown again."""
    cells = (
        "↳" if repeat else company_cell(s),
        "" if repeat else what_cell(s),
        "" if repeat else STAGE_LABELS[s.stage],
        role_cell(r),
        location_cell(s),
        apply_cell(r),
        r.confirmed.isoformat(),
    )
    return "| " + " | ".join(cells) + " |"


def table(pairs: Iterable[tuple[Startup, Role]]) -> list[str]:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    prev = None
    for s, r in pairs:
        lines.append(row(s, r, repeat=s is prev))
        prev = s
    return lines


def _sort_key(pair: tuple[Startup, Role]) -> tuple:
    s, r = pair
    return (s.name.casefold(), r.title.casefold(), (r.term or "").casefold())


def is_active(r: Role, today: date) -> bool:
    return r.status == "open" and not is_stale(r.confirmed, today)


def render_readme(startups: Iterable[Startup], today: date, header: str = "", footer: str = "") -> str:
    startups = sorted(startups, key=lambda s: s.name.casefold())
    active = [(s, r) for s in startups for r in s.roles if is_active(r, today)]
    inactive = [(s, r) for s in startups for r in s.roles if not is_active(r, today)]
    idle = [s for s in startups if not s.roles]

    n_open = len(active)
    n_companies = len({s.name for s, _ in active})
    out = [GENERATED_NOTICE, ""]
    if header:
        out += [header.strip(), ""]
    out += [f"**{n_open} open role{'s' if n_open != 1 else ''} at {n_companies} "
            f"startup{'s' if n_companies != 1 else ''}.**", ""]

    sections = (("Featured", [p for p in active if p[0].featured]), ("All startups", [p for p in active if not p[0].featured]))
    for title, pairs in sections:
        if not pairs:
            continue
        out += [f"## {title}", ""]
        for level, level_title in LEVEL_SECTIONS:
            subset = sorted((p for p in pairs if p[1].level == level), key=_sort_key)
            if subset:
                out += [f"### {level_title}", ""] + table(subset) + [""]

    if not active:
        out += ["_No open roles right now. Check back soon._", ""]

    if idle:
        names = ", ".join(link(s.name, s.website) for s in idle)
        out += [f"**Also tracking** (no open roles right now): {names}", ""]

    if inactive:
        out += [
            "<details>",
            f"<summary><b>Possibly stale / closed ({len(inactive)})</b>: closed roles, or roles not "
            f"confirmed in the last {STALE_AFTER_DAYS} days. They may still be open; check before applying.</summary>",
            "",
        ]
        out += table(sorted(inactive, key=_sort_key))
        out += ["", "</details>", ""]

    if footer:
        out += [footer.strip(), ""]
    return "\n".join(out).rstrip() + "\n"


def render_to_file(startups: Iterable[Startup], today: date, templates_dir: Path, out_path: Path) -> bool:
    """Write README.md. Returns True if the file changed."""
    header = _read(templates_dir / "header.md")
    footer = _read(templates_dir / "footer.md")
    text = render_readme(startups, today, header, footer)
    old = out_path.read_text(encoding="utf-8") if out_path.exists() else None
    if old == text:
        return False
    out_path.write_text(text, encoding="utf-8")
    return True


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""
