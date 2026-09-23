from datetime import date, datetime, timezone

from conftest import REPO, SAMPLE_DATA, TODAY, email_role, role, startup, write
from startup_jobs.cli import main
from startup_jobs.validate import validate_dir


def messages(report, level="error"):
    return [f"{p.file}: {p.message}" for p in report.problems if p.level == level]


def test_repo_data_is_valid():
    """The real listings, checked against the real current date."""
    today = datetime.now(timezone.utc).date()
    report = validate_dir(REPO / "data", today, root=REPO)
    assert report.ok, messages(report)


def test_sample_data_is_valid():
    report = validate_dir(SAMPLE_DATA, TODAY)
    assert report.ok, messages(report)
    assert len(report.startups) == 3


def test_valid_file(data_dir):
    write(data_dir, "widget-co.yaml", startup())
    report = validate_dir(data_dir, TODAY)
    assert report.ok and not report.warnings


def test_error_names_file_and_field(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[email_role(contact_consent=False)]))
    [err] = messages(validate_dir(data_dir, TODAY))
    assert err.startswith("data/widget-co.yaml: roles[0]: contact_consent: true is required")


def test_filename_must_match_name(data_dir):
    write(data_dir, "widgets.yaml", startup())
    assert messages(validate_dir(data_dir, TODAY)) == [
        "data/widgets.yaml: filename must be widget-co.yaml to match name 'Widget Co'"
    ]


def test_yml_extension_rejected(data_dir):
    write(data_dir, "widget-co.yml", startup())
    assert "must use the .yaml extension" in messages(validate_dir(data_dir, TODAY))[0]


def test_invalid_yaml(data_dir):
    write(data_dir, "widget-co.yaml", "name: [unclosed\n")
    assert "invalid YAML" in messages(validate_dir(data_dir, TODAY))[0]


def test_duplicate_yaml_key_is_an_error(data_dir):
    write(data_dir, "widget-co.yaml", "name: Widget Co\nname: Other\n")
    assert "duplicate key 'name'" in messages(validate_dir(data_dir, TODAY))[0]


def test_non_mapping_file(data_dir):
    write(data_dir, "widget-co.yaml", "- just a list\n")
    assert "must contain a YAML mapping" in messages(validate_dir(data_dir, TODAY))[0]


def test_duplicate_startup_by_name(data_dir):
    write(data_dir, "widget-co.yaml", startup())
    # Same name, different file and website: the second file also has the wrong filename.
    write(data_dir, "widget-co-2.yaml", startup(website="https://other.example.com", roles=[]))
    errs = messages(validate_dir(data_dir, TODAY))
    assert any("startup 'Widget Co' is already listed in" in e for e in errs)


def test_duplicate_startup_by_website(data_dir):
    write(data_dir, "widget-co.yaml", startup())
    write(data_dir, "gadget-co.yaml", startup(name="Gadget Co", website="https://www.widgetco.example.com/", roles=[]))
    assert messages(validate_dir(data_dir, TODAY)) == [
        "data/widget-co.yaml: website widgetco.example.com is already used by data/gadget-co.yaml"
    ]


def test_duplicate_role_url_across_files(data_dir):
    write(data_dir, "widget-co.yaml", startup())
    write(data_dir, "gadget-co.yaml", startup(
        name="Gadget Co", website="https://gadget.example.com",
        roles=[role(url="https://JOBS.example.com/widgetco/swe-intern/")],
    ))
    errs = messages(validate_dir(data_dir, TODAY))
    assert len(errs) == 1 and "roles[0].url" in errs[0] and "already used by" in errs[0]


def test_duplicate_role_identity(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(), role(url="https://jobs.example.com/other")]))
    assert "duplicate role" in messages(validate_dir(data_dir, TODAY))[0]


def test_same_title_different_level_is_fine(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(), role(level="new-grad", url="https://jobs.example.com/ng")]))
    assert validate_dir(data_dir, TODAY).ok


def test_future_confirmed_date(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(confirmed=date(2026, 12, 1))]))
    assert "is in the future" in messages(validate_dir(data_dir, TODAY))[0]


def test_stale_is_warning_not_error(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(confirmed=date(2026, 7, 23))]))  # 61 days
    report = validate_dir(data_dir, TODAY)
    assert report.ok
    assert "last confirmed 61 days ago" in messages(report, "warning")[0]


def test_sixty_days_is_not_stale(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(confirmed=date(2026, 7, 24))]))
    assert not validate_dir(data_dir, TODAY).warnings


def test_closed_old_role_no_warning(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[role(confirmed=date(2025, 1, 1), status="closed")]))
    assert not validate_dir(data_dir, TODAY).warnings


def test_personal_email_warns(data_dir):
    write(data_dir, "widget-co.yaml", startup(roles=[email_role(contact="jane@widgetco.example.com")]))
    report = validate_dir(data_dir, TODAY)
    assert report.ok and "personal address" in messages(report, "warning")[0]


def test_cli_exit_codes(data_dir, capsys, monkeypatch):
    monkeypatch.chdir(data_dir.parent)
    write(data_dir, "widget-co.yaml", startup())
    assert main(["--today", "2026-09-22", "validate"]) == 0
    write(data_dir, "widget-co.yaml", startup(typo=1))
    assert main(["--today", "2026-09-22", "validate"]) == 1
    assert "ERROR: data/widget-co.yaml: typo: unknown field" in capsys.readouterr().out
