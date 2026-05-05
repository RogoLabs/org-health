# org-health

RogoLabs GitHub Actions health dashboard. Updates daily via GitHub Actions.

## Setup

1. Create repo secret `ORG_ADMIN_TOKEN` with a PAT that has `admin:org` scope
2. Enable GitHub Pages from `docs/` folder on the main branch

## Local Development

```bash
# Collect data locally (requires GH_TOKEN env var with admin:org scope)
export GH_TOKEN=$(gh auth token)
python scripts/collect.py
```

## Dashboard

View at: https://rogolabs.github.io/org-health/
