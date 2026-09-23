from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SAMPLE_DATA = Path(__file__).resolve().parent / "fixtures" / "data"  # fictional startups
TODAY = date(2026, 9, 22)


def role(**overrides) -> dict:
    base = {
        "title": "Software Engineering Intern",
        "level": "intern",
        "category": "SWE",
        "term": "Summer 2027",
        "apply_method": "ats",
        "url": "https://jobs.example.com/widgetco/swe-intern",
        "confirmed": date(2026, 9, 1),
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def startup(**overrides) -> dict:
    base = {
        "name": "Widget Co",
        "website": "https://widgetco.example.com",
        "one_liner": "Widgets for everyone",
        "stage": "seed",
        "locations": ["Austin, TX"],
        "remote_ok": False,
        "roles": [role()],
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def email_role(**overrides) -> dict:
    """An email-apply role. Pass a field as None to drop it."""
    fields = {"apply_method": "email", "url": None, "contact": "jobs@widgetco.example.com", "contact_consent": True}
    fields.update(overrides)
    return role(**fields)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


def write(data_dir: Path, filename: str, data: dict | str) -> Path:
    path = data_dir / filename
    text = data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    return path
