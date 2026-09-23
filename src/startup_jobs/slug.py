"""Kebab-case helpers shared by the validator and the issue bot."""

from __future__ import annotations

import re
import unicodedata

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    """Turn a startup name into the expected data filename stem.

    "Acme Robotics" -> "acme-robotics", "Bits & Bolts" -> "bits-and-bolts".
    """
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def is_kebab(text: str) -> bool:
    return bool(KEBAB_RE.match(text))
