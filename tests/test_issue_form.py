import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from conftest import REPO, TODAY
from startup_jobs import issue_form as f
from startup_jobs.cli import main
from startup_jobs.issue_form import IssueFormError, apply_issue, parse_sections
from startup_jobs.validate import validate_dir

FIXTURES = Path(__file__).parent / "fixtures" / "issues"
TEMPLATES = REPO / ".github" / "ISSUE_TEMPLATE"


def body(name: str) -> str:
    return (FIXTURES / f"{name}.md").read_text()


@pytest.fixture
def repo_data(tmp_path: Path) -> Path:
    """A copy of the real data/ directory to apply issues to."""
    d = tmp_path / "data"
    shutil.copytree(REPO / "data", d)
    return d


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_parse_sections():
    s = parse_sections(body("add_new_email"))
    assert s["Startup name"] == "Lumen Labs"
    assert s["Headcount"] == ""  # _No response_
    assert s["Locations"] == "San Francisco, CA\nRemote"


def test_add_new_startup_email(repo_data):
    path, summary = apply_issue(body("add_new_email"), repo_data, TODAY, ["add-startup"])
    assert path.name == "lumen-labs.yaml"
    assert summary == "Add Lumen Labs (new startup) with role 'Data Science Intern'"
    data = load(path)
    assert list(data)[:4] == ["name", "website", "one_liner", "stage"]
    assert data["locations"] == ["San Francisco, CA", "Remote"]
    assert data["remote_ok"] is True
    assert data["affiliations"] == ["Demo Fund S26", "Example Angels"]
    assert "headcount" not in data
    [r] = data["roles"]
    assert r == {
        "title": "Data Science Intern", "level": "intern", "category": "Data", "term": "Summer 2027",
        "apply_method": "email", "contact": "jobs@lumenlabs.example.com", "contact_consent": True,
        "confirmed": TODAY, "apply_tips": "Resume + 2 lines on why",
    }  # the URL typed alongside an email role is dropped
    assert validate_dir(repo_data, TODAY).ok


def test_add_role_to_existing_startup(repo_data):
    before = load(repo_data / "acme-robotics.yaml")
    path, summary = apply_issue(body("add_existing_ats"), repo_data, TODAY, ["add-startup", "approved"])
    after = load(path)
    assert summary == "Add role 'Product Design Intern' to Acme Robotics"
    assert after["roles"][:-1] == before["roles"]
    assert after["roles"][-1]["url"] == "https://jobs.lever.example.com/acme/design-intern"
    assert after["website"] == before["website"]
    assert validate_dir(repo_data, TODAY).ok


def test_add_duplicate_role_rejected(repo_data):
    apply_issue(body("add_existing_ats"), repo_data, TODAY)
    with pytest.raises(IssueFormError, match="already lists"):
        apply_issue(body("add_existing_ats"), repo_data, TODAY)


def test_email_without_consent_rejected(repo_data):
    with pytest.raises(IssueFormError) as exc:
        apply_issue(body("add_email_no_consent"), repo_data, TODAY, ["add-startup"])
    assert any("Email consent" in m and "must be checked" in m for m in exc.value.messages)
    assert not (repo_data / "lumen-labs.yaml").exists()


def test_new_startup_missing_fields_lists_all_errors(repo_data):
    text = "### Startup name\n\nBrand New\n\n### Role title\n\nIntern\n\n### How to apply\n\nEmail\n"
    with pytest.raises(IssueFormError) as exc:
        apply_issue(text, repo_data, TODAY, ["add-startup"])
    joined = "\n".join(exc.value.messages)
    for label in ("Website", "One-liner", "Stage", "Locations", "Level", "Category", "Contact email"):
        assert label in joined


def test_bad_dropdown_value(repo_data):
    text = body("add_new_email").replace("### Stage\n\nseed", "### Stage\n\nseries-z")
    with pytest.raises(IssueFormError, match="series-z"):
        apply_issue(text, repo_data, TODAY, ["add-startup"])


def test_update_reconfirms_with_case_insensitive_match(repo_data):
    path, summary = apply_issue(body("update_reconfirm"), repo_data, TODAY, ["update-role"])
    role = next(r for r in load(path)["roles"] if r["level"] == "new-grad")
    assert role["confirmed"] == TODAY
    assert role["title"] == "Controls Engineer, New Grad"  # unchanged
    assert summary == "Update role 'Controls Engineer, New Grad' at Acme Robotics"


def test_update_switch_to_email(repo_data):
    path, _ = apply_issue(body("update_switch_to_email"), repo_data, TODAY, ["update-role"])
    role = next(r for r in load(path)["roles"] if r["title"] == "Hardware Engineering Intern")
    assert role["apply_method"] == "email"
    assert role["contact"] == "careers@acmerobotics.example.com"
    assert role["contact_consent"] is True
    assert "url" not in role
    assert role["confirmed"] == date(2026, 9, 21)
    assert role["apply_tips"] == "Mention robotics projects you've built"
    assert validate_dir(repo_data, TODAY).ok


def test_update_new_contact_requires_fresh_consent(repo_data):
    text = body("update_switch_to_email").replace("- [X]", "- [ ]")
    with pytest.raises(IssueFormError, match="must be checked"):
        apply_issue(text, repo_data, TODAY, ["update-role"])


def test_update_unknown_role_lists_existing(repo_data):
    text = body("update_reconfirm").replace("controls engineer, new grad", "Chief Vibes Officer")
    with pytest.raises(IssueFormError) as exc:
        apply_issue(text, repo_data, TODAY, ["update-role"])
    assert "No role at Acme Robotics" in str(exc.value)
    assert "Controls Engineer, New Grad (new-grad, Full-time 2027)" in str(exc.value)


def test_update_unknown_startup(repo_data):
    text = body("update_reconfirm").replace("Acme Robotics", "Nope Inc")
    with pytest.raises(IssueFormError, match="No startup named 'Nope Inc'"):
        apply_issue(text, repo_data, TODAY, ["update-role"])


def test_update_bad_date(repo_data):
    text = body("update_switch_to_email").replace("2026-09-21", "Sept 21")
    with pytest.raises(IssueFormError, match="YYYY-MM-DD"):
        apply_issue(text, repo_data, TODAY, ["update-role"])


def test_close_role(repo_data):
    path, summary = apply_issue(body("close_role"), repo_data, TODAY, ["close-role"])
    role = next(r for r in load(path)["roles"] if r["title"] == "ML Engineering Intern")
    assert role["status"] == "closed"
    assert role["contact_consent"] is True  # untouched
    assert summary == "Mark role 'ML Engineering Intern' at Quillstack as closed"


def test_detect_form_without_labels(repo_data):
    _, summary = apply_issue(body("close_role"), repo_data, TODAY, labels=[])
    assert summary.startswith("Mark role")


def test_unrecognised_body():
    with pytest.raises(IssueFormError, match="Could not tell which form"):
        apply_issue("hello", Path("/nonexistent"), TODAY)


def test_cli_apply_issue_success_and_failure(tmp_path, repo_data, monkeypatch, capsys):
    monkeypatch.chdir(repo_data.parent)
    good, bad, summary = tmp_path / "good.md", tmp_path / "bad.md", tmp_path / "summary.txt"
    good.write_text(body("close_role"))
    bad.write_text(body("add_email_no_consent"))
    args = ["--today", "2026-09-22", "apply-issue", "--labels", "approved,close-role"]
    assert main(args + ["--body-file", str(good), "--summary-file", str(summary)]) == 0
    assert summary.read_text().startswith("Mark role")
    capsys.readouterr()
    assert main(args[:-2] + ["--labels", "add-startup", "--body-file", str(bad)]) == 1
    assert "must be checked" in capsys.readouterr().out


def test_cli_apply_issue_reports_validation_failure(tmp_path, repo_data, monkeypatch, capsys):
    """A change that parses but breaks a repo-wide rule (duplicate URL) must fail."""
    monkeypatch.chdir(repo_data.parent)
    text = body("add_existing_ats").replace(
        "https://jobs.lever.example.com/acme/design-intern", "https://forms.example.com/tidewater-bizops"
    )
    (tmp_path / "dup.md").write_text(text)
    assert main(["--today", "2026-09-22", "apply-issue", "--body-file", str(tmp_path / "dup.md")]) == 1
    assert "already used by" in capsys.readouterr().out


# --------------------------------------------------------------- template sync

TEMPLATE_FILES = {"add-startup-role.yml": f.FORM_ADD, "update-role.yml": f.FORM_UPDATE, "close-role.yml": f.FORM_CLOSE}


def template_fields(filename: str) -> dict[str, dict]:
    doc = yaml.safe_load((TEMPLATES / filename).read_text())
    return {el["attributes"]["label"]: el for el in doc["body"] if el["type"] != "markdown"}, doc


@pytest.mark.parametrize("filename,form", TEMPLATE_FILES.items())
def test_templates_match_parser(filename, form):
    fields, doc = template_fields(filename)
    assert f.FORM_LABELS[doc["labels"][0]] == form
    missing = set(f.LABELS_BY_FORM[form]) - set(fields)
    assert not missing, f"{filename} lacks labels the parser reads: {missing}"
    for label, el in fields.items():
        if el["type"] == "dropdown":
            options = set(el["attributes"]["options"])
            known = [set(f.LEVEL_OPTIONS), set(f.APPLY_OPTIONS), set(f.YES_NO), set(f.STATUS_OPTIONS),
                     set(f.STAGES), set(f.HEADCOUNTS), set(f.CATEGORIES)]
            assert options in known, f"{filename}: dropdown {label!r} options don't match the parser"
        if el["type"] == "checkboxes":
            assert [o["label"] for o in el["attributes"]["options"]] == [f.CONSENT_TEXT]


def test_dropdown_mappings_cover_schema_enums():
    assert set(f.APPLY_OPTIONS.values()) == set(f.APPLY_METHODS)
    assert set(f.LEVEL_OPTIONS.values()) == set(f.LEVELS)
