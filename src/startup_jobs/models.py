"""The data schema. Every data/*.yaml file must parse into `Startup`.

`extra="forbid"` is deliberate: a misspelled field must fail validation
instead of being silently ignored.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

STAGES = ("pre-seed", "seed", "series-a", "series-b", "series-c+", "bootstrapped", "unknown")
HEADCOUNTS = ("1-10", "11-50", "51-200", "201-500", "501+")
LEVELS = ("intern", "new-grad")
CATEGORIES = ("SWE", "ML/AI", "Data", "Product", "Design", "Hardware", "Growth/Marketing", "Ops/BizOps", "Other")
APPLY_METHODS = ("ats", "email", "form")
STATUSES = ("open", "closed")

ONE_LINER_MAX = 120

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

Stage = Literal[STAGES]
Headcount = Literal[HEADCOUNTS]
Level = Literal[LEVELS]
Category = Literal[CATEGORIES]
ApplyMethod = Literal[APPLY_METHODS]
Status = Literal[STATUSES]

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def check_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("must start with https:// (or http://)")
    host = parsed.hostname or ""
    if "." not in host or any(c.isspace() for c in value):
        raise ValueError(f"is not a valid URL: {value!r}")
    return value


def check_email(value: str) -> str:
    if not EMAIL_RE.match(value):
        raise ValueError(f"is not a valid email address: {value!r}")
    return value.lower()


Url = Annotated[Text, AfterValidator(check_url)]
Email = Annotated[Text, AfterValidator(check_email)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(_Model):
    title: Text
    level: Level
    category: Category
    term: Optional[Text] = None
    apply_method: ApplyMethod
    url: Optional[Url] = None
    contact: Optional[Email] = None
    contact_consent: Optional[StrictBool] = None
    confirmed: date
    status: Status = "open"
    apply_tips: Optional[Text] = None

    @model_validator(mode="after")
    def _check_apply_method(self) -> "Role":
        method = self.apply_method
        if method in ("ats", "form"):
            if not self.url:
                raise ValueError(f"url is required when apply_method is {method}")
            if self.contact is not None or self.contact_consent is not None:
                raise ValueError(f"contact/contact_consent are only allowed when apply_method is email (this role uses {method})")
        else:  # email
            if not self.contact:
                raise ValueError("contact is required when apply_method is email")
            if self.contact_consent is not True:
                raise ValueError(
                    "contact_consent: true is required when apply_method is email "
                    "(only publish addresses the startup approved)"
                )
            if self.url is not None:
                raise ValueError("url is not allowed when apply_method is email; use contact instead")
        return self

    @property
    def identity(self) -> tuple[str, str, str]:
        """How a role is identified within a startup (used by update/close forms)."""
        return (self.title.casefold(), self.level, (self.term or "").casefold())

    @property
    def apply_link(self) -> str:
        return f"mailto:{self.contact}" if self.apply_method == "email" else str(self.url)


class Startup(_Model):
    name: Text
    website: Url
    one_liner: Annotated[Text, StringConstraints(max_length=ONE_LINER_MAX)]
    stage: Stage
    headcount: Optional[Headcount] = None
    locations: Annotated[List[Text], Field(min_length=1)]
    remote_ok: StrictBool = False
    affiliations: List[Text] = []
    featured: StrictBool = False
    notes: Optional[Text] = None
    roles: List[Role]


# Canonical key order, used when the issue bot writes YAML.
STARTUP_FIELDS = list(Startup.model_fields)
ROLE_FIELDS = list(Role.model_fields)
