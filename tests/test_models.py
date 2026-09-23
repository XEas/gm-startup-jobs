from datetime import date

import pytest
from pydantic import ValidationError

from conftest import email_role, role, startup
from startup_jobs.loader import format_validation_error
from startup_jobs.models import Startup
from startup_jobs.slug import slugify


def errors_for(data: dict) -> list[str]:
    with pytest.raises(ValidationError) as exc:
        Startup.model_validate(data)
    return format_validation_error(exc.value)


def test_valid_startup_parses():
    s = Startup.model_validate(startup())
    assert s.roles[0].status == "open"
    assert s.featured is False


def test_empty_roles_allowed():
    assert Startup.model_validate(startup(roles=[])).roles == []


def test_unknown_startup_field_is_an_error():
    assert errors_for(startup(websit="https://x.example.com")) == [
        "websit: unknown field (check the spelling; see CONTRIBUTING.md for allowed fields)"
    ]


def test_unknown_role_field_is_an_error():
    msgs = errors_for(startup(roles=[role(titel="oops")]))
    assert msgs == ["roles[0].titel: unknown field (check the spelling; see CONTRIBUTING.md for allowed fields)"]


@pytest.mark.parametrize("field", ["name", "website", "one_liner", "stage", "locations", "roles"])
def test_required_startup_fields(field):
    data = startup()
    del data[field]
    assert errors_for(data) == [f"{field}: required field is missing"]


def test_one_liner_length_limit():
    msgs = errors_for(startup(one_liner="x" * 121))
    assert msgs[0].startswith("one_liner:") and "120" in msgs[0]


@pytest.mark.parametrize("field,value", [("stage", "series-d"), ("headcount", "10-20")])
def test_enums(field, value):
    assert errors_for(startup(**{field: value}))[0].startswith(f"{field}:")


def test_role_enums():
    assert errors_for(startup(roles=[role(category="Engineering")]))[0].startswith("roles[0].category:")
    assert errors_for(startup(roles=[role(level="senior")]))[0].startswith("roles[0].level:")


def test_bool_must_be_real_bool():
    assert errors_for(startup(remote_ok="maybe"))[0].startswith("remote_ok:")


def test_bad_urls():
    assert "https://" in errors_for(startup(website="acme.example.com"))[0]
    assert errors_for(startup(roles=[role(url="https://no spaces.example.com")]))[0].startswith("roles[0].url:")
    assert errors_for(startup(roles=[role(url="ftp://files.example.com/x")]))[0].startswith("roles[0].url:")


@pytest.mark.parametrize("method", ["ats", "form"])
def test_link_methods_require_url(method):
    msgs = errors_for(startup(roles=[role(apply_method=method, url=None)]))
    assert msgs == [f"roles[0]: url is required when apply_method is {method}"]


def test_link_methods_reject_contact():
    msgs = errors_for(startup(roles=[role(contact="jobs@x.example.com", contact_consent=True)]))
    assert "only allowed when apply_method is email" in msgs[0]


def test_email_role_valid():
    s = Startup.model_validate(startup(roles=[email_role()]))
    assert s.roles[0].apply_link == "mailto:jobs@widgetco.example.com"


@pytest.mark.parametrize("consent", [None, False, "yes"])
def test_email_requires_consent_true(consent):
    msgs = errors_for(startup(roles=[email_role(contact_consent=consent)]))
    assert any("contact_consent" in m for m in msgs)


def test_email_requires_contact_and_rejects_url():
    assert "contact is required" in errors_for(startup(roles=[email_role(contact=None)]))[0]
    assert "url is not allowed" in errors_for(startup(roles=[email_role(url="https://x.example.com/a")]))[0]


def test_bad_email():
    assert "valid email" in errors_for(startup(roles=[email_role(contact="jobs-at-example")]))[0]


def test_confirmed_must_be_date():
    assert errors_for(startup(roles=[role(confirmed="last week")]))[0].startswith("roles[0].confirmed:")
    assert Startup.model_validate(startup(roles=[role(confirmed="2026-09-01")])).roles[0].confirmed == date(2026, 9, 1)


@pytest.mark.parametrize("name,slug", [
    ("Acme Robotics", "acme-robotics"),
    ("Bits & Bolts", "bits-and-bolts"),
    ("Café.ai", "cafe-ai"),
    ("  X  ", "x"),
])
def test_slugify(name, slug):
    assert slugify(name) == slug
