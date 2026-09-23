# CLAUDE.md

Guidance for AI-assisted edits to this repo. These rules are non-negotiable.

## What this repo is

A curated list of startup internship and new-grad roles. `data/*.yaml` (one file per startup) is the **only source of truth**. `src/startup_jobs/` validates those files and renders `README.md`. GitHub Actions validate PRs, regenerate the README on main, and turn approved issue-form submissions into PRs.

## Critical rules

1. **Never edit `README.md` by hand.** Change `data/`, `templates/header.md`, `templates/footer.md`, or `src/startup_jobs/render.py`, then run `make render`.
2. **Schema strictness stays.** Models use `extra="forbid"`; unknown fields must fail. Don't loosen that, and don't add silent defaults that could hide a typo. A new field has to go into `models.py`, `CONTRIBUTING.md` (tables + example), and the issue forms and parser if it's user-submittable.
3. **Email consent.** Never publish an email contact unless `contact_consent: true` reflects real approval from the startup. Never add `contact_consent: true` on anyone's behalf, never weaken the validator or bot check, and prefer role addresses (`jobs@`, `careers@`).
4. **No affiliations or maintainer identity.** Don't mention or imply any university, school, club, or organization behind this project, and don't name who maintains it. This covers code, docs, examples, test fixtures, issue templates, and commit messages. (Startups' own `affiliations`, like accelerators, are data, not project affiliation.)
5. **Example and test data is fictional.** Use made-up startups and `*.example.com` domains.
6. **Filenames** are `slugify(name) + ".yaml"` (see `src/startup_jobs/slug.py`).
7. **Issue forms and the parser must agree.** Labels and dropdown options in `.github/ISSUE_TEMPLATE/*.yml` must match the constants in `src/startup_jobs/issue_form.py`. `tests/test_issue_form.py::test_templates_match_parser` enforces this.
8. **Bot changes go through PRs.** The issue workflow opens a PR; it never pushes data to main. Only the README render workflow commits to main.
9. **Untrusted input.** Issue bodies and titles only reach shell via env vars or files, never via `${{ }}` interpolation inside `run:`.

## Commands

```sh
make install   # create .venv
make check     # validate + pytest + render; run before finishing any change
make validate  # schema + cross-file checks (errors fail, stale dates warn)
make render    # regenerate README.md
```

## Layout

- `src/startup_jobs/models.py`: pydantic schema and enums
- `src/startup_jobs/validate.py`: cross-file checks (filename, duplicates, dates, email warnings)
- `src/startup_jobs/render.py`: README generation (featured first, intern/new-grad tables, stale/closed collapsed)
- `src/startup_jobs/issue_form.py`: issue-form body → YAML change
- `.github/workflows/`: `validate.yml` (PR CI), `render-readme.yml` (main + weekly), `issue-to-pr.yml` (`approved` label)

## GitHub setup

- Labels: `approved`, `add-startup`, `update-role`, `close-role`
- Settings → Actions → General: Workflow permissions "Read and write", and "Allow GitHub Actions to create and approve pull requests"
- Optional secret `BOT_TOKEN` (fine-grained PAT: Contents, Pull requests, Issues read/write on this repo). Bot PRs then trigger CI, and the README bot can push past branch protection.
