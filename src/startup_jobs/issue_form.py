"""Turn a GitHub issue-form body into a change in data/.

GitHub renders issue forms as Markdown:

    ### Startup name

    Acme Robotics

    ### Headcount

    _No response_

Section labels below must match the `label:` values in .github/ISSUE_TEMPLATE/*.yml
exactly (a test enforces this).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml

from startup_jobs.loader import read_yaml
from startup_jobs.models import APPLY_METHODS, CATEGORIES, HEADCOUNTS, LEVELS, ROLE_FIELDS, STAGES, STARTUP_FIELDS
from startup_jobs.slug import slugify

FORM_ADD = "add"
FORM_UPDATE = "update"
FORM_CLOSE = "close"
FORM_LABELS = {"add-startup": FORM_ADD, "update-role": FORM_UPDATE, "close-role": FORM_CLOSE}

NO_RESPONSE = "_No response_"
CONSENT_TEXT = "The startup approved publishing this email address"

# Dropdown option text -> schema value.
LEVEL_OPTIONS = {"Internship": "intern", "New grad": "new-grad"}
APPLY_OPTIONS = {
    "ATS or careers page link": "ats",
    "Email": "email",
    "Application form link": "form",
}
YES_NO = {"Yes": True, "No": False}
STATUS_OPTIONS = {"No change": None, "Open": "open", "Closed": "closed"}

# Labels shared by several forms.
L_NAME = "Startup name"
L_TITLE = "Role title"
L_LEVEL = "Level"
L_TERM = "Term"
L_CATEGORY = "Category"
L_APPLY = "How to apply"
L_URL = "Application URL"
L_CONTACT = "Contact email"
L_CONSENT = "Email consent"
L_TIPS = "Apply tips"

# Add form (startup-level).
L_WEBSITE = "Website"
L_ONE_LINER = "One-liner"
L_STAGE = "Stage"
L_HEADCOUNT = "Headcount"
L_LOCATIONS = "Locations"
L_REMOTE = "Remote OK?"
L_AFFILIATIONS = "Affiliations"

# Update form.
L_NEW_TITLE = "New role title"
L_NEW_CATEGORY = "New category"
L_NEW_TERM = "New term"
L_NEW_APPLY = "New way to apply"
L_NEW_URL = "New application URL"
L_NEW_CONTACT = "New contact email"
L_NEW_TIPS = "New apply tips"
L_STATUS = "Status"
L_CONFIRMED = "Confirmed open on"

LABELS_BY_FORM = {
    FORM_ADD: [L_NAME, L_WEBSITE, L_ONE_LINER, L_STAGE, L_HEADCOUNT, L_LOCATIONS, L_REMOTE, L_AFFILIATIONS,
               L_TITLE, L_LEVEL, L_CATEGORY, L_TERM, L_APPLY, L_URL, L_CONTACT, L_CONSENT, L_TIPS],
    FORM_UPDATE: [L_NAME, L_TITLE, L_LEVEL, L_TERM, L_NEW_TITLE, L_NEW_CATEGORY, L_NEW_TERM, L_NEW_APPLY,
                  L_NEW_URL, L_NEW_CONTACT, L_CONSENT, L_NEW_TIPS, L_STATUS, L_CONFIRMED],
    FORM_CLOSE: [L_NAME, L_TITLE, L_LEVEL, L_TERM],
}


class IssueFormError(Exception):
    def __init__(self, messages: list[str] | str):
        self.messages = [messages] if isinstance(messages, str) else messages
        super().__init__("\n".join(self.messages))


# --------------------------------------------------------------------------- parsing

def parse_sections(body: str) -> dict[str, str]:
    """Split an issue-form body into {label: raw value}. Empty answers become ""."""
    sections: dict[str, str] = {}
    current: Optional[str] = None
    lines: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = _clean("\n".join(lines))
            current, lines = m.group(1), []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = _clean("\n".join(lines))
    return sections


def _clean(value: str) -> str:
    value = value.strip()
    return "" if value == NO_RESPONSE else value


def detect_form(labels: list[str], sections: dict[str, str]) -> str:
    for label in labels:
        if label.strip() in FORM_LABELS:
            return FORM_LABELS[label.strip()]
    if L_NEW_TITLE in sections:
        return FORM_UPDATE
    if L_APPLY in sections:
        return FORM_ADD
    if L_TITLE in sections and L_NAME in sections:
        return FORM_CLOSE
    raise IssueFormError(
        "Could not tell which form this issue uses. Please open a new issue with one of the templates."
    )


class _Fields:
    """Typed access to parsed sections that collects every error before failing."""

    def __init__(self, sections: dict[str, str]):
        self.sections = sections
        self.errors: list[str] = []

    def text(self, label: str, required: bool = False) -> Optional[str]:
        value = " ".join(self.sections.get(label, "").split())
        if not value:
            if required:
                self.errors.append(f"**{label}** is required.")
            return None
        return value

    def lines(self, label: str, split_commas: bool = False) -> list[str]:
        raw = self.sections.get(label, "")
        parts = re.split(r"[\n,]" if split_commas else r"\n", raw)
        return [" ".join(p.strip().lstrip("-*").split()) for p in parts if p.strip().lstrip("-*").strip()]

    def choice(self, label: str, options: dict[str, Any] | tuple, required: bool = False) -> Any:
        value = self.text(label, required=required)
        if value is None:
            return None
        mapping = options if isinstance(options, dict) else {o: o for o in options}
        if value not in mapping:
            self.errors.append(f"**{label}**: {value!r} is not one of: {', '.join(mapping)}.")
            return None
        return mapping[value]

    def checked(self, label: str) -> bool:
        return bool(re.search(r"^\s*-\s*\[[xX]\]", self.sections.get(label, ""), re.M))

    def date(self, label: str) -> Optional[date]:
        value = self.text(label)
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            self.errors.append(f"**{label}**: {value!r} is not a date in YYYY-MM-DD format.")
            return None

    def raise_if_errors(self) -> None:
        if self.errors:
            raise IssueFormError(self.errors)


# --------------------------------------------------------------------------- YAML I/O

class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):  # indent list items
        return super().increase_indent(flow, False)


def _ordered(data: dict, order: list[str]) -> dict:
    out = {k: data[k] for k in order if k in data}
    out.update({k: v for k, v in data.items() if k not in out})
    return out


def dump_startup(data: dict) -> str:
    data = _ordered(data, STARTUP_FIELDS)
    data["roles"] = [_ordered(r, ROLE_FIELDS) for r in data.get("roles") or []]
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)


def _set(d: dict, key: str, value: Any) -> None:
    if value is None or value == []:
        return
    d[key] = value


# --------------------------------------------------------------------------- appliers

def apply_issue(body: str, data_dir: Path, today: date, labels: Optional[list[str]] = None) -> tuple[Path, str]:
    """Apply the issue to data/. Returns (changed file, one-line summary)."""
    sections = parse_sections(body)
    form = detect_form(labels or [], sections)
    f = _Fields(sections)
    name = f.text(L_NAME, required=True)
    f.raise_if_errors()
    path = data_dir / f"{slugify(name)}.yaml"
    existing = read_yaml(path) if path.exists() else None
    if existing is not None and not isinstance(existing, dict):
        raise IssueFormError(f"{path.name} is not a valid data file; a maintainer needs to fix it by hand.")

    if form == FORM_ADD:
        data, summary = _apply_add(f, name, existing, today)
    elif form == FORM_UPDATE:
        data, summary = _apply_update(f, name, existing, today)
    else:
        data, summary = _apply_close(f, name, existing)

    path.write_text(dump_startup(data), encoding="utf-8")
    return path, summary


def _role_apply_fields(role: dict, method: Optional[str], url: Optional[str], contact: Optional[str],
                       consent: bool) -> None:
    """Set url/contact for the chosen method and drop fields that don't apply to it."""
    if method:
        role["apply_method"] = method
    if url:
        role["url"] = url
    if contact and contact.lower() != str(role.get("contact", "")).lower():
        role["contact"] = contact
        role.pop("contact_consent", None)  # a new address needs fresh consent
    if consent and role.get("contact"):
        role["contact_consent"] = True
    if role.get("apply_method") == "email":
        role.pop("url", None)
    else:
        role.pop("contact", None)
        role.pop("contact_consent", None)


def _check_email_consent(f: _Fields, role: dict) -> None:
    if role.get("apply_method") == "email":
        if not role.get("contact"):
            f.errors.append(f"**{L_CONTACT}** is required when applying by email.")
        elif role.get("contact_consent") is not True:
            f.errors.append(
                f"**{L_CONSENT}** must be checked for email roles. We only publish addresses the startup "
                "approved. Edit the issue, tick the box, and a maintainer will re-approve it."
            )
    elif not role.get("url"):
        f.errors.append(f"**{L_URL}** is required unless applying by email.")


def _apply_add(f: _Fields, name: str, existing: Optional[dict], today: date) -> tuple[dict, str]:
    startup_updates: dict = {}
    _set(startup_updates, "website", f.text(L_WEBSITE, required=existing is None))
    _set(startup_updates, "one_liner", f.text(L_ONE_LINER, required=existing is None))
    _set(startup_updates, "stage", f.choice(L_STAGE, STAGES, required=existing is None))
    _set(startup_updates, "headcount", f.choice(L_HEADCOUNT, HEADCOUNTS))
    locations = f.lines(L_LOCATIONS)
    if existing is None and not locations:
        f.errors.append(f"**{L_LOCATIONS}** is required for a new startup.")
    _set(startup_updates, "locations", locations)
    remote = f.choice(L_REMOTE, YES_NO)
    if remote is not None:
        startup_updates["remote_ok"] = remote
    _set(startup_updates, "affiliations", f.lines(L_AFFILIATIONS, split_commas=True))

    role: dict = {}
    _set(role, "title", f.text(L_TITLE, required=True))
    _set(role, "level", f.choice(L_LEVEL, LEVEL_OPTIONS, required=True))
    _set(role, "category", f.choice(L_CATEGORY, CATEGORIES, required=True))
    _set(role, "term", f.text(L_TERM))
    method = f.choice(L_APPLY, APPLY_OPTIONS, required=True)
    _role_apply_fields(role, method, f.text(L_URL), f.text(L_CONTACT), f.checked(L_CONSENT))
    role["confirmed"] = today
    _set(role, "apply_tips", f.text(L_TIPS))
    if method:
        _check_email_consent(f, role)
    f.raise_if_errors()

    if existing is None:
        data = {"name": name, **startup_updates, "roles": [role]}
        return data, f"Add {name} (new startup) with role {role['title']!r}"

    data = dict(existing)
    data.update(startup_updates)
    roles = list(data.get("roles") or [])
    if _find_roles(roles, role["title"], role["level"], role.get("term")):
        raise IssueFormError(
            f"{name} already lists {role['title']!r} ({role['level']}, {role.get('term') or 'no term'}). "
            "Use the “Update a role” form instead."
        )
    roles.append(role)
    data["roles"] = roles
    return data, f"Add role {role['title']!r} to {name}"


def _find_roles(roles: list[dict], title: str, level: Optional[str], term: Optional[str]) -> list[int]:
    """Indexes of roles matching title+level, narrowed by term when one is given."""
    matches = [
        i for i, r in enumerate(roles)
        if str(r.get("title", "")).casefold() == title.casefold() and r.get("level") == level
    ]
    if term is not None:
        matches = [i for i in matches if str(roles[i].get("term") or "").casefold() == term.casefold()]
    return matches


def _locate_role(f: _Fields, name: str, existing: Optional[dict]) -> tuple[dict, list[dict], int]:
    title = f.text(L_TITLE, required=True)
    level = f.choice(L_LEVEL, LEVEL_OPTIONS, required=True)
    term = f.text(L_TERM)
    f.raise_if_errors()
    if existing is None:
        raise IssueFormError(f"No startup named {name!r} is listed (looked for data/{slugify(name)}.yaml).")
    roles = [dict(r) for r in existing.get("roles") or []]
    matches = _find_roles(roles, title, level, term)
    if len(matches) != 1:
        listed = "\n".join(
            f"- {r.get('title')} ({r.get('level')}, {r.get('term') or 'no term'})" for r in roles
        ) or "- (none)"
        problem = "No role" if not matches else "More than one role"
        raise IssueFormError(
            f"{problem} at {name} matches title {title!r}, level {level!r}"
            f"{f', term {term!r}' if term else ''}. Roles currently listed:\n{listed}"
        )
    return dict(existing), roles, matches[0]


def _apply_update(f: _Fields, name: str, existing: Optional[dict], today: date) -> tuple[dict, str]:
    data, roles, i = _locate_role(f, name, existing)
    role = roles[i]
    _set(role, "title", f.text(L_NEW_TITLE))
    _set(role, "category", f.choice(L_NEW_CATEGORY, CATEGORIES))
    _set(role, "term", f.text(L_NEW_TERM))
    method = f.choice(L_NEW_APPLY, APPLY_OPTIONS)
    _role_apply_fields(role, method, f.text(L_NEW_URL), f.text(L_NEW_CONTACT), f.checked(L_CONSENT))
    _set(role, "apply_tips", f.text(L_NEW_TIPS))
    status = f.choice(L_STATUS, STATUS_OPTIONS)
    if status:
        role["status"] = status
    role["confirmed"] = f.date(L_CONFIRMED) or today
    _check_email_consent(f, role)
    f.raise_if_errors()
    roles[i] = role
    data["roles"] = roles
    return data, f"Update role {role['title']!r} at {name}"


def _apply_close(f: _Fields, name: str, existing: Optional[dict]) -> tuple[dict, str]:
    data, roles, i = _locate_role(f, name, existing)
    roles[i]["status"] = "closed"
    data["roles"] = roles
    return data, f"Mark role {roles[i]['title']!r} at {name} as closed"
