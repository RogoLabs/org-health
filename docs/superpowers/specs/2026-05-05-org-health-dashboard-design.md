# Org Health Dashboard — Design Spec

## Overview

A GitHub Pages static site that provides daily visibility into RogoLabs org GitHub Actions usage, workflow reliability, and runner contention. Hosted in the `RogoLabs/org-health` repo.

## Goals

1. Show which repos consume the most Actions minutes and storage
2. Surface workflow success/failure rates across the org
3. Highlight run duration outliers
4. List recent failures with actionable error details
5. Flag runner contention events (jobs that timed out waiting for a hosted runner)

## Architecture

```
.github/workflows/update.yml  (daily cron, 6am UTC + workflow_dispatch)
    → scripts/collect.py       (Python 3.12, zero external deps — uses urllib)
    → docs/data/*.json         (flat JSON data files)

docs/index.html                (static site: Tailwind CSS + Alpine.js + Chart.js, all via CDN)
    → fetches docs/data/*.json client-side
    → renders dashboard
```

GitHub Pages serves the `docs/` folder on the default branch.

## Data Collection

`scripts/collect.py` produces 6 JSON files:

| File                             | API Source                                            | Contents                                                 |
| -------------------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| `docs/data/billing.json`         | `GET /organizations/{org}/settings/billing/usage`     | Monthly minutes + storage per repo (last 5 months)       |
| `docs/data/workflow-health.json` | `GET /repos/{org}/{repo}/actions/runs`                | Success/failure/cancelled counts per repo (last 30 days) |
| `docs/data/durations.json`       | `GET /repos/{org}/{repo}/actions/runs`                | Average run duration per workflow                        |
| `docs/data/failures.json`        | `GET /repos/{org}/{repo}/actions/runs?status=failure` | Last 20 failed runs org-wide with error annotations      |
| `docs/data/contention.json`      | Derived from failure annotations                      | Jobs that failed with "runner not acquired" message      |
| `docs/data/meta.json`            | Generated                                             | Last update timestamp, list of repos scanned             |

### Authentication

- **Billing endpoint** requires `admin:org` scope — uses a PAT stored as repo secret `ORG_ADMIN_TOKEN`
- **Workflow runs endpoints** use the default `GITHUB_TOKEN` (sufficient for public repos)

### Collection Logic

1. Fetch org repo list from `GET /orgs/RogoLabs/repos?type=public`
2. For each repo, fetch workflow runs (last 30 days), aggregate health/duration/failure stats
3. Fetch billing usage data (single call, returns all repos)
4. Parse billing response into per-repo monthly breakdowns
5. Scan failure annotations for "runner not acquired" pattern → contention events
6. Write all JSON files to `docs/data/`

## Frontend

Single-page dashboard (`docs/index.html`) with these sections:

1. **Header** — "RogoLabs Org Health" title + last-updated timestamp from `meta.json`
2. **Minutes Overview** — Bar chart (Chart.js) showing monthly minutes by repo, last 5 months, sortable
3. **Storage** — Table with per-repo GB-hours from billing data
4. **Workflow Health** — Cards per repo showing success rate percentage with color coding:
   - Green: >90% success
   - Yellow: 70–90% success
   - Red: <70% success
5. **Run Durations** — Table of workflows sorted by average duration, outliers highlighted
6. **Recent Failures** — List with repo name, workflow, error reason, timestamp, link to run on GitHub
7. **Runner Contention** — Flagged jobs that timed out waiting for a runner

### Tech Stack (all CDN, no build step)

- Tailwind CSS — styling
- Alpine.js — client-side reactivity
- Chart.js — bar chart for minutes

## Workflow

`.github/workflows/update.yml`:

```yaml
name: Update Org Health Data
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Collect data
        env:
          GH_TOKEN: ${{ secrets.ORG_ADMIN_TOKEN }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/collect.py
      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/data/
          git diff --staged --quiet || git commit -m "chore: update org health data [skip ci]" && git push
```

## Repo Structure

```
org-health/
├── .github/
│   └── workflows/
│       └── update.yml
├── docs/
│   ├── data/
│   │   ├── billing.json
│   │   ├── workflow-health.json
│   │   ├── durations.json
│   │   ├── failures.json
│   │   ├── contention.json
│   │   └── meta.json
│   └── index.html
├── scripts/
│   └── collect.py
└── README.md
```

## Secrets Required

| Secret            | Scope       | Purpose                       |
| ----------------- | ----------- | ----------------------------- |
| `ORG_ADMIN_TOKEN` | `admin:org` | Access billing usage endpoint |

The default `GITHUB_TOKEN` handles all other API calls.

## Out of Scope

- Alerting/notifications (can be added later)
- Private repo visibility (only public repos tracked)
- Cost projections or budget alerts (all public repos = free)
- Historical trend storage beyond what the billing API returns
