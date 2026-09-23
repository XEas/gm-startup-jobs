import re
from datetime import date

from conftest import REPO, SAMPLE_DATA, TODAY, email_role, role, startup
from startup_jobs.cli import main
from startup_jobs.models import Startup
from startup_jobs.render import GENERATED_NOTICE, cell, render_readme


def S(**kw) -> Startup:
    return Startup.model_validate(startup(**kw))


def section(text: str, heading: str) -> str:
    """Text from `heading` up to the next heading of the same or higher level."""
    level = heading.split(" ")[0]
    start = text.index(heading + "\n")
    rest = text[start + len(heading) + 1:]
    ends = [i for i in (rest.find(f"\n{h} ") for h in ("#" * n for n in range(1, len(level) + 1))) if i >= 0]
    ends.append(rest.find("<details>") if "<details>" in rest else len(rest))
    return rest[: min(ends)]


def test_notice_header_footer():
    out = render_readme([S()], TODAY, header="# Title", footer="bye")
    assert out.startswith(GENERATED_NOTICE)
    assert "# Title" in out and out.rstrip().endswith("bye")


def test_table_columns_and_row():
    out = render_readme([S(remote_ok=True, affiliations=["Demo Fund"])], TODAY)
    assert "| Company | What they do | Stage | Role | Location | Apply | Confirmed |" in out
    row = next(line for line in out.splitlines() if line.startswith("| **[Widget Co]"))
    assert "[Widget Co](https://widgetco.example.com)" in row
    assert "Demo Fund" in row and "| Seed |" in row
    assert "Austin, TX (remote ok)" in row
    assert "[Apply](https://jobs.example.com/widgetco/swe-intern)" in row
    assert "| 2026-09-01 |" in row


def test_repeated_company_rows_collapse():
    s = S(roles=[role(title="A", url="https://jobs.example.com/a"), role(title="B", url="https://jobs.example.com/b")])
    rows = [line for line in render_readme([s], TODAY).splitlines() if "jobs.example.com/" in line]
    assert rows[0].startswith("| **[Widget Co]")
    assert rows[1].startswith("| ↳ |  |  | B<br>")


def test_email_role_uses_mailto():
    out = render_readme([S(roles=[email_role(apply_tips="Resume + 2 lines")])], TODAY)
    assert "[Email](mailto:jobs@widgetco.example.com)" in out
    assert "Resume + 2 lines" in out


def test_featured_first_then_alphabetical():
    zeta = S(name="Zeta", website="https://zeta.example.com", featured=True,
             roles=[role(url="https://jobs.example.com/zeta")])
    beta = S(name="beta", website="https://beta.example.com", roles=[role(url="https://jobs.example.com/b")])
    alpha = S(name="Alpha", website="https://alpha.example.com", roles=[role(url="https://jobs.example.com/a")])
    out = render_readme([beta, zeta, alpha], TODAY)
    assert out.index("### Featured") < out.index("### All startups")
    assert out.index("[Zeta]") < out.index("[Alpha]") < out.index("[beta]")
    assert "[Zeta]" in section(out, "### Featured")
    assert "[Zeta]" not in section(out, "### All startups")


def test_interns_and_new_grads_split():
    s = S(roles=[role(), role(title="Founding Engineer", level="new-grad", url="https://jobs.example.com/ng")])
    out = render_readme([s], TODAY)
    interns, new_grad = section(out, "#### Internships"), section(out, "#### New Grad")
    assert "Software Engineering Intern" in interns and "Founding Engineer" not in interns
    assert "Founding Engineer" in new_grad


def test_closed_and_stale_go_to_collapsed_section():
    s = S(roles=[
        role(title="Open One", url="https://jobs.example.com/1"),
        role(title="Closed One", url="https://jobs.example.com/2", status="closed"),
        role(title="Stale One", url="https://jobs.example.com/3", confirmed=date(2026, 7, 1)),
    ])
    out = render_readme([s], TODAY)
    main_part, details = out.split("<details>")
    assert "Open One" in main_part
    assert "Closed One" not in main_part and "Stale One" not in main_part
    assert "Possibly stale / closed (2)" in details
    assert "Closed One" in details and "Stale One" in details
    assert "https://jobs.example.com/2" not in details  # closed roles have no apply link


def test_no_details_when_everything_fresh():
    assert "<details>" not in render_readme([S()], TODAY)


def test_startup_without_roles_listed_as_tracking():
    out = render_readme([S(roles=[])], TODAY)
    assert "Also tracking" in out and "No open roles" in out


def test_empty_data_renders():
    out = render_readme([], TODAY)
    assert "0 open roles at 0 startups" in out and "No open roles" in out


def test_notes_rendered():
    assert "Great mentors" in render_readme([S(notes="Great mentors")], TODAY)


def test_cell_escapes_pipes_and_newlines():
    assert cell("a | b\nc") == "a \\| b c"


def test_pipe_in_data_does_not_break_table():
    out = render_readme([S(one_liner="Build | ship")], TODAY)
    row = next(line for line in out.splitlines() if line.startswith("| **[Widget Co]"))
    assert len(re.findall(r"(?<!\\)\|", row)) == 8  # 7 columns -> 8 unescaped pipes
    assert "Build \\| ship" in row


def test_deterministic():
    s = [S()]
    assert render_readme(s, TODAY) == render_readme(s, TODAY)


def test_cli_render_and_check(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    out = tmp_path / "README.md"
    args = ["--today", "2026-09-22", "--data-dir", str(SAMPLE_DATA)]
    assert main(args + ["render", "--output", str(out)]) == 0
    assert main(args + ["check-readme", "--output", str(out)]) == 0
    out.write_text(out.read_text() + "hand edit\n")
    assert main(args + ["check-readme", "--output", str(out)]) == 1
