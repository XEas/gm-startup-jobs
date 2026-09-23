# Contributing

Thanks for helping students find startup roles! Every listing lives in one YAML file per startup in [`data/`](data/). `README.md` is generated from those files, so **never edit README.md by hand**. Your edits would be overwritten.

There are two ways to contribute.

## Option 1: Issue forms (no coding needed)

Use this if you're a student, a recruiter, or a startup listing itself.

| I want to… | Use this form |
|---|---|
| List a new startup, or add a role to one already listed | [Add a startup / role](../../issues/new?template=add-startup-role.yml) |
| Re-confirm a role is still open, or change its details | [Update a role](../../issues/new?template=update-role.yml) |
| Report that a role has closed | [Mark role closed](../../issues/new?template=close-role.yml) |

What happens next:

1. A maintainer reviews the issue and adds the `approved` label.
2. A bot turns the issue into a change to `data/`, validates it, and opens a pull request that references the issue.
3. If something is wrong (a missing field, or email consent not ticked), the bot comments on the issue with the exact problem. Edit the issue, and a maintainer re-applies `approved`.
4. When the pull request is merged, the issue closes and the README updates automatically.

## Option 2: Pull request

1. Add or edit `data/<startup-name>.yaml` (see the schema below).
2. Run the checks locally (optional, but it saves a round trip):

   ```sh
   make install   # first time only: creates .venv and installs dependencies
   make check     # validate + tests + render README
   ```

   You don't need to commit `README.md`. It's regenerated after merge.
3. Open a pull request. CI runs the same checks.

## Schema

The filename must be the kebab-case form of `name`: `Acme Robotics` → `data/acme-robotics.yaml`, and `Bits & Bolts` → `data/bits-and-bolts.yaml`.

**Unknown or misspelled fields are errors**, so a typo never silently drops a company.

### Startup fields

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Company name as it should appear. |
| `website` | yes | `https://…` |
| `one_liner` | yes | What they build, 120 characters max. |
| `stage` | yes | `pre-seed`, `seed`, `series-a`, `series-b`, `series-c+`, `bootstrapped`, `unknown` |
| `headcount` | no | `1-10`, `11-50`, `51-200`, `201-500`, `501+` |
| `locations` | yes | List, at least one entry, e.g. `San Francisco, CA`, `Remote`. |
| `remote_ok` | no | `true` / `false` (default `false`). |
| `affiliations` | no | List of free text, e.g. accelerator batch or investors. |
| `featured` | no | `true` shows the startup in the Featured section. Set by maintainers. |
| `notes` | no | Short curator note shown under the one-liner. |
| `roles` | yes | List of roles. May be empty (`roles: []`) if we track the startup but nothing is open. |

### Role fields

| Field | Required | Notes |
|---|---|---|
| `title` | yes | |
| `level` | yes | `intern` or `new-grad` |
| `category` | yes | `SWE`, `ML/AI`, `Data`, `Product`, `Design`, `Hardware`, `Growth/Marketing`, `Ops/BizOps`, `Other` |
| `term` | no | e.g. `Summer 2027`, `Fall 2026`, `Full-time 2027`, `Rolling` |
| `apply_method` | yes | `ats`, `email`, or `form` (see below) |
| `url` | for `ats` / `form` | Greenhouse / Lever / Ashby / careers page, or an intake form link. Not allowed for `email`. |
| `contact` | for `email` | Email address. Prefer role addresses like `jobs@`. Not allowed for `ats` / `form`. |
| `contact_consent` | for `email` | Must be `true`. |
| `confirmed` | yes | `YYYY-MM-DD`, the date the role was last confirmed open. Can't be in the future. |
| `status` | no | `open` (default) or `closed` |
| `apply_tips` | no | e.g. `Send resume + 2 lines on why` |

### The email consent rule

We **only publish an email address if the startup has approved it**. An `email` role without `contact_consent: true` fails validation. Please don't add `contact_consent: true` unless the startup actually said yes. Use a role address (`jobs@`, `careers@`) rather than a person's address; the validator warns about anything that looks personal.

### Other checks

- The same startup can't appear in two files (matched by name or website domain).
- A role URL can't appear twice anywhere in `data/`.
- Within a startup, the combination of `title` + `level` + `term` must be unique. This is how the update and close forms find a role.

### Freshness

A role whose `confirmed` date is more than **60 days** old is still valid; CI only warns about it. It moves from the main tables into the collapsed **Possibly stale / closed** section of the README until someone re-confirms it (with the "Update a role" form, or by bumping `confirmed`). Closed roles live there too.

### Full example

```yaml
name: Acme Robotics
website: https://acmerobotics.example.com
one_liner: Autonomous forklifts for mid-size warehouses
stage: series-a
headcount: 51-200
locations:
  - Pittsburgh, PA
  - Remote
remote_ok: true
affiliations:
  - Example Accelerator W25
featured: false
notes: Interns ship to real warehouses in week one.
roles:
  - title: Software Engineering Intern
    level: intern
    category: SWE
    term: Summer 2027
    apply_method: ats
    url: https://jobs.ashbyhq.example.com/acme-robotics/swe-intern
    confirmed: 2026-09-15
  - title: Founding Operations Associate
    level: new-grad
    category: Ops/BizOps
    term: Full-time 2027
    apply_method: email
    contact: jobs@acmerobotics.example.com
    contact_consent: true
    confirmed: 2026-09-15
    apply_tips: Send resume + 2 lines on why
  - title: Data Intern
    level: intern
    category: Data
    term: Fall 2026
    apply_method: form
    url: https://forms.example.com/acme-data-intern
    confirmed: 2026-08-01
    status: closed
```

## For maintainers

- `make validate`, `make render`, `make test`, and `make check` are the local commands. `python -m startup_jobs --help` lists everything.
- The bot rewrites a data file whenever it applies an issue, so YAML comments inside that file are not kept.
- Setup notes for the GitHub automation (labels, permissions, tokens) are in [CLAUDE.md](CLAUDE.md#github-setup).
