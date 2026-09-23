"""Load data/*.yaml files and turn problems into readable messages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from startup_jobs.models import Startup


@dataclass(frozen=True)
class Problem:
    level: str  # "error" or "warning"
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()}: {self.file}: {self.message}"


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys instead of keeping the last one."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_UniqueKeyLoader)


def format_loc(loc: tuple) -> str:
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "(top level)"


def format_validation_error(err: ValidationError) -> list[str]:
    messages = []
    for item in err.errors():
        # Drop pydantic's internal type tags such as "function-after[...]".
        loc = tuple(p for p in item["loc"] if not (isinstance(p, str) and ("[" in p or p in ("str", "date"))))
        where = format_loc(loc)
        kind = item["type"]
        if kind == "extra_forbidden":
            msg = "unknown field (check the spelling; see CONTRIBUTING.md for allowed fields)"
        elif kind == "missing":
            msg = "required field is missing"
        else:
            msg = item["msg"].removeprefix("Value error, ")
        messages.append(f"{where}: {msg}")
    return messages


def load_startup(path: Path, display: Optional[str] = None) -> tuple[Optional[Startup], list[Problem]]:
    name = display or str(path)
    try:
        raw = read_yaml(path)
    except yaml.YAMLError as exc:
        return None, [Problem("error", name, f"invalid YAML: {exc}".replace("\n", " "))]
    if not isinstance(raw, dict):
        return None, [Problem("error", name, "file must contain a YAML mapping (name: ..., website: ..., roles: [...])")]
    try:
        return Startup.model_validate(raw), []
    except ValidationError as exc:
        return None, [Problem("error", name, msg) for msg in format_validation_error(exc)]
