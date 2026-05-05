# Org Health Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Pages dashboard showing RogoLabs org Actions usage, workflow health, and runner contention.

**Architecture:** A daily GitHub Actions workflow runs a Python script that collects data from GitHub's billing and workflow APIs, writes JSON files to `docs/data/`, and a static HTML page renders the dashboard client-side using Tailwind, Alpine.js, and Chart.js via CDN.

**Tech Stack:** Python 3.12 (stdlib only — urllib, json), GitHub REST API, Tailwind CSS, Alpine.js, Chart.js, GitHub Pages.

---

## File Structure

```
org-health/
├── .github/
│   └── workflows/
│       └── update.yml          # Daily cron + manual trigger
├── docs/
│   ├── data/                   # JSON data files (generated)
│   │   ├── billing.json
│   │   ├── workflow-health.json
│   │   ├── durations.json
│   │   ├── failures.json
│   │   ├── contention.json
│   │   └── meta.json
│   └── index.html              # Dashboard UI
├── scripts/
│   ├── collect.py              # Main data collection script
│   └── test_collect.py         # Tests for collection logic
├── README.md
└── .gitignore
```

---

### Task 1: Repository Setup

**Files:**

- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd ~/Documents/Github/org-health
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.env
.venv/
```

- [ ] **Step 3: Create README.md**

````markdown
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
````

## Dashboard

View at: https://rogolabs.github.io/org-health/

````

- [ ] **Step 4: Create docs/data directory with placeholder**

```bash
mkdir -p docs/data
echo '{}' > docs/data/.gitkeep.json
````

- [ ] **Step 5: Initial commit**

```bash
git add .
git commit -m "chore: initialize org-health repo"
```

---

### Task 2: Data Collection — Meta and Repo List

**Files:**

- Create: `scripts/collect.py`
- Create: `scripts/test_collect.py`

- [ ] **Step 1: Write the failing test for fetch_repos and write_meta**

Create `scripts/test_collect.py`:

```python
import json
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import collect


def test_fetch_repos_returns_list_of_names():
    mock_response = json.dumps([
        {"name": "repo-a", "visibility": "public"},
        {"name": "repo-b", "visibility": "public"},
    ]).encode()

    with patch("collect.api_get", return_value=json.loads(mock_response)):
        repos = collect.fetch_repos("TestOrg")

    assert repos == ["repo-a", "repo-b"]


def test_write_meta_creates_valid_json(tmp_path):
    output_dir = tmp_path / "data"
    output_dir.mkdir()

    collect.write_meta(output_dir, ["repo-a", "repo-b"])

    meta = json.loads((output_dir / "meta.json").read_text())
    assert "updated_at" in meta
    assert meta["repos"] == ["repo-a", "repo-b"]
    assert meta["org"] == "RogoLabs"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: FAIL — `collect` module not found

- [ ] **Step 3: Write minimal implementation**

Create `scripts/collect.py`:

```python
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ORG = "RogoLabs"
BASE_URL = "https://api.github.com"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data"


def get_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN or GITHUB_TOKEN environment variable required")
    return token


def api_get(url):
    token = get_token()
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_get_paginated(url, max_pages=5):
    results = []
    page = 1
    while page <= max_pages:
        sep = "&" if "?" in url else "?"
        page_url = f"{url}{sep}page={page}&per_page=100"
        data = api_get(page_url)
        if isinstance(data, list):
            if not data:
                break
            results.extend(data)
        else:
            break
        page += 1
    return results


def fetch_repos(org):
    repos = api_get_paginated(f"{BASE_URL}/orgs/{org}/repos?type=public")
    return sorted([r["name"] for r in repos])


def write_meta(output_dir, repos):
    meta = {
        "org": ORG,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos,
    }
    Path(output_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def write_json(output_dir, filename, data):
    Path(output_dir / filename).write_text(json.dumps(data, indent=2))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = fetch_repos(ORG)
    write_meta(OUTPUT_DIR, repos)
    print(f"Found {len(repos)} repos: {', '.join(repos)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py scripts/test_collect.py
git commit -m "feat: add data collection script with repo list and meta"
```

---

### Task 3: Data Collection — Billing

**Files:**

- Modify: `scripts/collect.py`
- Modify: `scripts/test_collect.py`

- [ ] **Step 1: Write the failing test for billing collection**

Append to `scripts/test_collect.py`:

```python
def test_collect_billing_parses_usage_items():
    raw_response = {
        "usageItems": [
            {
                "date": "2026-04-01T00:00:00Z",
                "product": "actions",
                "sku": "Actions Linux",
                "quantity": 36952.0,
                "unitType": "Minutes",
                "pricePerUnit": 0.006,
                "grossAmount": 221.712,
                "discountAmount": 221.712,
                "netAmount": 0.0,
                "organizationName": "RogoLabs",
                "repositoryName": "CVE-Updates",
            },
            {
                "date": "2026-04-01T00:00:00Z",
                "product": "actions",
                "sku": "Actions storage",
                "quantity": 1511.614,
                "unitType": "GigabyteHours",
                "pricePerUnit": 0.00033602,
                "grossAmount": 0.507,
                "discountAmount": 0.507,
                "netAmount": 0.0,
                "organizationName": "RogoLabs",
                "repositoryName": "GhostCVEs",
            },
        ]
    }

    with patch("collect.api_get", return_value=raw_response):
        billing = collect.collect_billing("RogoLabs")

    assert billing["minutes"]["CVE-Updates"]["2026-04"] == 36952.0
    assert billing["storage"]["GhostCVEs"]["2026-04"] == 1511.614
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py::test_collect_billing_parses_usage_items -v`
Expected: FAIL — `collect_billing` not defined

- [ ] **Step 3: Implement collect_billing**

Add to `scripts/collect.py` before `main()`:

```python
def collect_billing(org):
    url = f"{BASE_URL}/organizations/{org}/settings/billing/usage"
    data = api_get(url)

    minutes = {}
    storage = {}

    for item in data.get("usageItems", []):
        if item["product"] != "actions":
            continue
        repo = item["repositoryName"]
        month = item["date"][:7]  # "2026-04-01T..." -> "2026-04"

        if item["unitType"] == "Minutes":
            minutes.setdefault(repo, {})[month] = item["quantity"]
        elif item["unitType"] == "GigabyteHours":
            storage.setdefault(repo, {})[month] = item["quantity"]

    return {"minutes": minutes, "storage": storage}
```

Update `main()`:

```python
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = fetch_repos(ORG)
    write_meta(OUTPUT_DIR, repos)
    print(f"Found {len(repos)} repos: {', '.join(repos)}")

    billing = collect_billing(ORG)
    write_json(OUTPUT_DIR, "billing.json", billing)
    print(f"Billing: {len(billing['minutes'])} repos with minutes, {len(billing['storage'])} with storage")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py scripts/test_collect.py
git commit -m "feat: add billing data collection"
```

---

### Task 4: Data Collection — Workflow Health

**Files:**

- Modify: `scripts/collect.py`
- Modify: `scripts/test_collect.py`

- [ ] **Step 1: Write the failing test for workflow health**

Append to `scripts/test_collect.py`:

```python
def test_collect_workflow_health_counts_conclusions():
    mock_runs = {
        "total_count": 4,
        "workflow_runs": [
            {"conclusion": "success", "name": "CI"},
            {"conclusion": "success", "name": "CI"},
            {"conclusion": "failure", "name": "CI"},
            {"conclusion": "cancelled", "name": "Deploy"},
        ],
    }

    with patch("collect.api_get", return_value=mock_runs):
        health = collect.collect_workflow_health("RogoLabs", ["my-repo"])

    assert health["my-repo"]["total"] == 4
    assert health["my-repo"]["success"] == 2
    assert health["my-repo"]["failure"] == 1
    assert health["my-repo"]["cancelled"] == 1
    assert health["my-repo"]["success_rate"] == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py::test_collect_workflow_health_counts_conclusions -v`
Expected: FAIL — `collect_workflow_health` not defined

- [ ] **Step 3: Implement collect_workflow_health**

Add to `scripts/collect.py` before `main()`:

```python
from datetime import timedelta


def collect_workflow_health(org, repos):
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    health = {}

    for repo in repos:
        url = f"{BASE_URL}/repos/{org}/{repo}/actions/runs?created=%3E{since}&per_page=100"
        try:
            data = api_get(url)
        except urllib.error.HTTPError:
            continue

        runs = data.get("workflow_runs", [])
        total = len(runs)
        success = sum(1 for r in runs if r["conclusion"] == "success")
        failure = sum(1 for r in runs if r["conclusion"] == "failure")
        cancelled = sum(1 for r in runs if r["conclusion"] == "cancelled")

        if total > 0:
            health[repo] = {
                "total": total,
                "success": success,
                "failure": failure,
                "cancelled": cancelled,
                "success_rate": round((success / total) * 100, 1),
            }

    return health
```

Update `main()`:

```python
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    repos = fetch_repos(ORG)
    write_meta(OUTPUT_DIR, repos)
    print(f"Found {len(repos)} repos: {', '.join(repos)}")

    billing = collect_billing(ORG)
    write_json(OUTPUT_DIR, "billing.json", billing)
    print(f"Billing: {len(billing['minutes'])} repos with minutes, {len(billing['storage'])} with storage")

    health = collect_workflow_health(ORG, repos)
    write_json(OUTPUT_DIR, "workflow-health.json", health)
    print(f"Workflow health: {len(health)} repos with runs")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py scripts/test_collect.py
git commit -m "feat: add workflow health collection"
```

---

### Task 5: Data Collection — Durations

**Files:**

- Modify: `scripts/collect.py`
- Modify: `scripts/test_collect.py`

- [ ] **Step 1: Write the failing test for durations**

Append to `scripts/test_collect.py`:

```python
def test_collect_durations_calculates_averages():
    mock_runs = {
        "total_count": 2,
        "workflow_runs": [
            {
                "name": "CI",
                "conclusion": "success",
                "run_started_at": "2026-05-01T10:00:00Z",
                "updated_at": "2026-05-01T10:05:00Z",
            },
            {
                "name": "CI",
                "conclusion": "success",
                "run_started_at": "2026-05-02T10:00:00Z",
                "updated_at": "2026-05-02T10:03:00Z",
            },
        ],
    }

    with patch("collect.api_get", return_value=mock_runs):
        durations = collect.collect_durations("RogoLabs", ["my-repo"])

    assert durations["my-repo"]["CI"]["avg_seconds"] == 240.0
    assert durations["my-repo"]["CI"]["run_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py::test_collect_durations_calculates_averages -v`
Expected: FAIL — `collect_durations` not defined

- [ ] **Step 3: Implement collect_durations**

Add to `scripts/collect.py` before `main()`:

```python
def collect_durations(org, repos):
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    durations = {}

    for repo in repos:
        url = f"{BASE_URL}/repos/{org}/{repo}/actions/runs?created=%3E{since}&status=completed&per_page=100"
        try:
            data = api_get(url)
        except urllib.error.HTTPError:
            continue

        workflows = {}
        for run in data.get("workflow_runs", []):
            if run["conclusion"] not in ("success", "failure"):
                continue
            name = run["name"]
            start = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
            duration = (end - start).total_seconds()
            workflows.setdefault(name, []).append(duration)

        if workflows:
            durations[repo] = {}
            for wf_name, times in workflows.items():
                durations[repo][wf_name] = {
                    "avg_seconds": round(sum(times) / len(times), 1),
                    "max_seconds": round(max(times), 1),
                    "min_seconds": round(min(times), 1),
                    "run_count": len(times),
                }

    return durations
```

Update `main()` to add after workflow health:

```python
    durations = collect_durations(ORG, repos)
    write_json(OUTPUT_DIR, "durations.json", durations)
    print(f"Durations: {len(durations)} repos with timing data")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py scripts/test_collect.py
git commit -m "feat: add workflow duration collection"
```

---

### Task 6: Data Collection — Failures and Contention

**Files:**

- Modify: `scripts/collect.py`
- Modify: `scripts/test_collect.py`

- [ ] **Step 1: Write the failing tests for failures and contention**

Append to `scripts/test_collect.py`:

```python
def test_collect_failures_returns_recent_failures():
    mock_runs = {
        "total_count": 1,
        "workflow_runs": [
            {
                "id": 123,
                "name": "Update Data",
                "conclusion": "failure",
                "created_at": "2026-05-05T13:44:20Z",
                "html_url": "https://github.com/RogoLabs/my-repo/actions/runs/123",
            },
        ],
    }
    mock_jobs = {
        "jobs": [
            {
                "id": 456,
                "name": "update",
                "conclusion": "failure",
            }
        ]
    }
    mock_annotations = [
        {
            "annotation_level": "failure",
            "message": "The job was not acquired by Runner of type hosted even after multiple attempts",
        }
    ]

    def mock_api_get(url):
        if "/actions/runs?" in url:
            return mock_runs
        if "/actions/runs/123/jobs" in url:
            return mock_jobs
        if "/check-runs/456/annotations" in url:
            return mock_annotations
        return {}

    with patch("collect.api_get", side_effect=mock_api_get):
        failures, contention = collect.collect_failures_and_contention("RogoLabs", ["my-repo"])

    assert len(failures) == 1
    assert failures[0]["repo"] == "my-repo"
    assert failures[0]["workflow"] == "Update Data"
    assert failures[0]["error"] == "The job was not acquired by Runner of type hosted even after multiple attempts"

    assert len(contention) == 1
    assert contention[0]["repo"] == "my-repo"


def test_collect_failures_non_contention_error():
    mock_runs = {
        "total_count": 1,
        "workflow_runs": [
            {
                "id": 789,
                "name": "CI",
                "conclusion": "failure",
                "created_at": "2026-05-05T10:00:00Z",
                "html_url": "https://github.com/RogoLabs/my-repo/actions/runs/789",
            },
        ],
    }
    mock_jobs = {
        "jobs": [
            {
                "id": 101,
                "name": "test",
                "conclusion": "failure",
            }
        ]
    }
    mock_annotations = [
        {
            "annotation_level": "failure",
            "message": "Process completed with exit code 1.",
        }
    ]

    def mock_api_get(url):
        if "/actions/runs?" in url:
            return mock_runs
        if "/actions/runs/789/jobs" in url:
            return mock_jobs
        if "/check-runs/101/annotations" in url:
            return mock_annotations
        return {}

    with patch("collect.api_get", side_effect=mock_api_get):
        failures, contention = collect.collect_failures_and_contention("RogoLabs", ["my-repo"])

    assert len(failures) == 1
    assert failures[0]["error"] == "Process completed with exit code 1."
    assert len(contention) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py::test_collect_failures_returns_recent_failures scripts/test_collect.py::test_collect_failures_non_contention_error -v`
Expected: FAIL — `collect_failures_and_contention` not defined

- [ ] **Step 3: Implement collect_failures_and_contention**

Add to `scripts/collect.py` before `main()`:

```python
CONTENTION_PATTERN = "not acquired by Runner"


def collect_failures_and_contention(org, repos, max_failures=20):
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    failures = []
    contention = []

    for repo in repos:
        url = f"{BASE_URL}/repos/{org}/{repo}/actions/runs?created=%3E{since}&status=failure&per_page=10"
        try:
            data = api_get(url)
        except urllib.error.HTTPError:
            continue

        for run in data.get("workflow_runs", []):
            error_msg = ""
            is_contention = False

            try:
                jobs_data = api_get(f"{BASE_URL}/repos/{org}/{repo}/actions/runs/{run['id']}/jobs")
                for job in jobs_data.get("jobs", []):
                    annotations = api_get(f"{BASE_URL}/repos/{org}/{repo}/check-runs/{job['id']}/annotations")
                    for ann in annotations:
                        if ann.get("annotation_level") == "failure":
                            error_msg = ann.get("message", "")
                            if CONTENTION_PATTERN in error_msg:
                                is_contention = True
                            break
                    if error_msg:
                        break
            except urllib.error.HTTPError:
                error_msg = "Unable to fetch error details"

            entry = {
                "repo": repo,
                "workflow": run["name"],
                "run_id": run["id"],
                "created_at": run["created_at"],
                "html_url": run["html_url"],
                "error": error_msg or "Unknown error",
            }

            failures.append(entry)
            if is_contention:
                contention.append(entry)

        if len(failures) >= max_failures:
            failures = failures[:max_failures]
            break

    failures.sort(key=lambda x: x["created_at"], reverse=True)
    contention.sort(key=lambda x: x["created_at"], reverse=True)
    return failures, contention
```

Update `main()` to add after durations:

```python
    failures, contention = collect_failures_and_contention(ORG, repos)
    write_json(OUTPUT_DIR, "failures.json", failures)
    write_json(OUTPUT_DIR, "contention.json", contention)
    print(f"Failures: {len(failures)} recent, {len(contention)} contention events")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Documents/Github/org-health && python -m pytest scripts/test_collect.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py scripts/test_collect.py
git commit -m "feat: add failure and contention detection"
```

---

### Task 7: Dashboard Frontend

**Files:**

- Create: `docs/index.html`

- [ ] **Step 1: Create the dashboard HTML**

Create `docs/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
	<head>
		<meta charset="UTF-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1.0" />
		<title>RogoLabs Org Health</title>
		<script src="https://cdn.tailwindcss.com"></script>
		<script
			defer
			src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"
		></script>
		<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
	</head>
	<body class="bg-gray-900 text-gray-100 min-h-screen">
		<div
			x-data="dashboard()"
			x-init="init()"
			class="max-w-7xl mx-auto px-4 py-8"
		>
			<!-- Header -->
			<header class="mb-8">
				<h1 class="text-3xl font-bold text-white">RogoLabs Org Health</h1>
				<p class="text-gray-400 mt-1">
					Last updated:
					<span
						x-text="meta.updated_at ? new Date(meta.updated_at).toLocaleString() : 'Loading...'"
					></span>
				</p>
			</header>

			<!-- Contention Alerts -->
			<template x-if="contention.length > 0">
				<div class="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-8">
					<h2 class="text-lg font-semibold text-red-300 mb-2">
						Runner Contention Events
					</h2>
					<p class="text-sm text-red-200 mb-3">
						Jobs that timed out waiting for a GitHub-hosted runner:
					</p>
					<template x-for="item in contention" :key="item.run_id">
						<div
							class="flex items-center justify-between py-2 border-t border-red-800"
						>
							<div>
								<span
									class="font-medium text-red-100"
									x-text="item.repo"
								></span>
								<span class="text-red-300 mx-2">/</span>
								<span class="text-red-200" x-text="item.workflow"></span>
							</div>
							<div class="flex items-center gap-4">
								<span
									class="text-sm text-red-400"
									x-text="new Date(item.created_at).toLocaleDateString()"
								></span>
								<a
									:href="item.html_url"
									target="_blank"
									class="text-red-300 hover:text-red-100 text-sm underline"
									>View</a
								>
							</div>
						</div>
					</template>
				</div>
			</template>

			<!-- Minutes Overview -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold mb-4">Actions Minutes by Repo</h2>
				<div class="bg-gray-800 rounded-lg p-4">
					<canvas id="minutesChart" height="100"></canvas>
				</div>
			</section>

			<!-- Workflow Health -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold mb-4">
					Workflow Health (Last 30 Days)
				</h2>
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
					<template
						x-for="[repo, stats] in Object.entries(workflowHealth)"
						:key="repo"
					>
						<div class="bg-gray-800 rounded-lg p-4">
							<div class="flex items-center justify-between mb-2">
								<h3 class="font-medium text-white truncate" x-text="repo"></h3>
								<span
									class="text-2xl font-bold"
									:class="stats.success_rate > 90 ? 'text-green-400' : stats.success_rate > 70 ? 'text-yellow-400' : 'text-red-400'"
									x-text="stats.success_rate + '%'"
								></span>
							</div>
							<div class="flex gap-4 text-sm text-gray-400">
								<span x-text="stats.success + ' passed'"></span>
								<span x-text="stats.failure + ' failed'"></span>
								<span x-text="stats.total + ' total'"></span>
							</div>
						</div>
					</template>
				</div>
			</section>

			<!-- Run Durations -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold mb-4">Average Run Durations</h2>
				<div class="bg-gray-800 rounded-lg overflow-hidden">
					<table class="w-full text-sm">
						<thead class="bg-gray-700">
							<tr>
								<th class="text-left px-4 py-2">Repo</th>
								<th class="text-left px-4 py-2">Workflow</th>
								<th class="text-right px-4 py-2">Avg Duration</th>
								<th class="text-right px-4 py-2">Max</th>
								<th class="text-right px-4 py-2">Runs</th>
							</tr>
						</thead>
						<tbody>
							<template
								x-for="row in durationRows"
								:key="row.repo + row.workflow"
							>
								<tr class="border-t border-gray-700">
									<td class="px-4 py-2" x-text="row.repo"></td>
									<td class="px-4 py-2" x-text="row.workflow"></td>
									<td
										class="px-4 py-2 text-right"
										:class="row.avg_seconds > 600 ? 'text-yellow-400' : 'text-gray-300'"
										x-text="formatDuration(row.avg_seconds)"
									></td>
									<td
										class="px-4 py-2 text-right text-gray-400"
										x-text="formatDuration(row.max_seconds)"
									></td>
									<td
										class="px-4 py-2 text-right text-gray-400"
										x-text="row.run_count"
									></td>
								</tr>
							</template>
						</tbody>
					</table>
				</div>
			</section>

			<!-- Storage -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold mb-4">Storage Usage</h2>
				<div class="bg-gray-800 rounded-lg overflow-hidden">
					<table class="w-full text-sm">
						<thead class="bg-gray-700">
							<tr>
								<th class="text-left px-4 py-2">Repo</th>
								<th class="text-right px-4 py-2">GB-Hours (Latest Month)</th>
							</tr>
						</thead>
						<tbody>
							<template x-for="[repo, gbh] in storageRows" :key="repo">
								<tr class="border-t border-gray-700">
									<td class="px-4 py-2" x-text="repo"></td>
									<td
										class="px-4 py-2 text-right text-gray-300"
										x-text="gbh.toFixed(1)"
									></td>
								</tr>
							</template>
						</tbody>
					</table>
				</div>
			</section>

			<!-- Recent Failures -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold mb-4">Recent Failures</h2>
				<div class="space-y-2">
					<template x-for="item in failures.slice(0, 20)" :key="item.run_id">
						<div
							class="bg-gray-800 rounded-lg p-3 flex items-center justify-between"
						>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2">
									<span
										class="font-medium text-white"
										x-text="item.repo"
									></span>
									<span class="text-gray-500">/</span>
									<span class="text-gray-300" x-text="item.workflow"></span>
								</div>
								<p
									class="text-sm text-gray-400 truncate mt-1"
									x-text="item.error"
								></p>
							</div>
							<div class="flex items-center gap-4 ml-4">
								<span
									class="text-sm text-gray-500 whitespace-nowrap"
									x-text="new Date(item.created_at).toLocaleDateString()"
								></span>
								<a
									:href="item.html_url"
									target="_blank"
									class="text-blue-400 hover:text-blue-300 text-sm whitespace-nowrap"
									>View Run</a
								>
							</div>
						</div>
					</template>
					<template x-if="failures.length === 0">
						<p class="text-gray-500 text-center py-4">No recent failures</p>
					</template>
				</div>
			</section>
		</div>

		<script>
			function dashboard() {
				return {
					meta: {},
					billing: {},
					workflowHealth: {},
					durations: {},
					failures: [],
					contention: [],
					durationRows: [],
					storageRows: [],

					async init() {
						const [meta, billing, health, durations, failures, contention] =
							await Promise.all([
								this.fetchJson("data/meta.json"),
								this.fetchJson("data/billing.json"),
								this.fetchJson("data/workflow-health.json"),
								this.fetchJson("data/durations.json"),
								this.fetchJson("data/failures.json"),
								this.fetchJson("data/contention.json"),
							]);

						this.meta = meta;
						this.billing = billing;
						this.workflowHealth = health;
						this.durations = durations;
						this.failures = failures;
						this.contention = contention;

						this.buildDurationRows();
						this.buildStorageRows();
						this.$nextTick(() => this.renderMinutesChart());
					},

					async fetchJson(path) {
						try {
							const resp = await fetch(path);
							if (!resp.ok) return {};
							return await resp.json();
						} catch {
							return {};
						}
					},

					buildDurationRows() {
						const rows = [];
						for (const [repo, workflows] of Object.entries(this.durations)) {
							for (const [workflow, stats] of Object.entries(workflows)) {
								rows.push({ repo, workflow, ...stats });
							}
						}
						rows.sort((a, b) => b.avg_seconds - a.avg_seconds);
						this.durationRows = rows;
					},

					buildStorageRows() {
						const storage = this.billing.storage || {};
						const rows = [];
						for (const [repo, months] of Object.entries(storage)) {
							const latestMonth = Object.keys(months).sort().pop();
							if (latestMonth) {
								rows.push([repo, months[latestMonth]]);
							}
						}
						rows.sort((a, b) => b[1] - a[1]);
						this.storageRows = rows;
					},

					renderMinutesChart() {
						const minutes = this.billing.minutes || {};
						const allMonths = new Set();
						for (const months of Object.values(minutes)) {
							Object.keys(months).forEach((m) => allMonths.add(m));
						}
						const labels = [...allMonths].sort();

						const colors = [
							"#3b82f6",
							"#ef4444",
							"#22c55e",
							"#f59e0b",
							"#8b5cf6",
							"#06b6d4",
							"#ec4899",
							"#14b8a6",
							"#f97316",
							"#6366f1",
						];

						const datasets = Object.entries(minutes)
							.map(([repo, months], i) => ({
								label: repo,
								data: labels.map((m) => months[m] || 0),
								backgroundColor: colors[i % colors.length],
							}))
							.sort((a, b) => {
								const sumA = a.data.reduce((s, v) => s + v, 0);
								const sumB = b.data.reduce((s, v) => s + v, 0);
								return sumB - sumA;
							});

						new Chart(document.getElementById("minutesChart"), {
							type: "bar",
							data: { labels, datasets },
							options: {
								responsive: true,
								plugins: {
									legend: { labels: { color: "#9ca3af" } },
								},
								scales: {
									x: { stacked: true, ticks: { color: "#9ca3af" } },
									y: {
										stacked: true,
										ticks: { color: "#9ca3af" },
										title: { display: true, text: "Minutes", color: "#9ca3af" },
									},
								},
							},
						});
					},

					formatDuration(seconds) {
						if (seconds < 60) return Math.round(seconds) + "s";
						if (seconds < 3600)
							return (
								Math.round(seconds / 60) + "m " + Math.round(seconds % 60) + "s"
							);
						return (
							Math.floor(seconds / 3600) +
							"h " +
							Math.round((seconds % 3600) / 60) +
							"m"
						);
					},
				};
			}
		</script>
	</body>
</html>
```

- [ ] **Step 2: Verify HTML is valid**

Run: `cd ~/Documents/Github/org-health && python -c "from html.parser import HTMLParser; HTMLParser().feed(open('docs/index.html').read()); print('Valid HTML')"`
Expected: "Valid HTML"

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat: add dashboard frontend"
```

---

### Task 8: GitHub Actions Workflow

**Files:**

- Create: `.github/workflows/update.yml`

- [ ] **Step 1: Create the workflow file**

```bash
mkdir -p ~/Documents/Github/org-health/.github/workflows
```

Create `.github/workflows/update.yml`:

```yaml
name: Update Org Health Data

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

permissions:
  contents: write

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
        run: python scripts/collect.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/data/
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: update org health data [skip ci]"
            git push
          fi
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd ~/Documents/Github/org-health && python -c "import yaml; yaml.safe_load(open('.github/workflows/update.yml')); print('Valid YAML')" 2>&1 || python3 -c "import json; print('PyYAML not installed, checking manually'); content=open('.github/workflows/update.yml').read(); assert 'on:' in content and 'jobs:' in content; print('Structure looks valid')"`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/update.yml
git commit -m "feat: add daily update workflow"
```

---

### Task 9: Local Test Run and Sample Data

**Files:**

- Modify: `docs/data/` (generated files)

- [ ] **Step 1: Run the collection script locally**

```bash
cd ~/Documents/Github/org-health
export GH_TOKEN=$(gh auth token)
python scripts/collect.py
```

Expected: Script completes, prints summary lines for each collection step.

- [ ] **Step 2: Verify generated JSON files**

```bash
ls -la docs/data/
python -c "
import json, pathlib
data_dir = pathlib.Path('docs/data')
for f in sorted(data_dir.glob('*.json')):
    data = json.loads(f.read_text())
    if isinstance(data, list):
        print(f'{f.name}: {len(data)} items')
    elif isinstance(data, dict):
        print(f'{f.name}: {len(data)} keys')
"
```

- [ ] **Step 3: Open dashboard in browser to verify rendering**

```bash
cd ~/Documents/Github/org-health/docs
python -m http.server 8080 &
open http://localhost:8080
```

Verify: All sections render, chart shows data, no console errors.

- [ ] **Step 4: Kill server, commit data**

```bash
kill %1
cd ~/Documents/Github/org-health
git add docs/data/
git commit -m "chore: add initial data collection"
```

---

### Task 10: Create Remote Repo and Push

**Files:** None (git operations only)

- [ ] **Step 1: Create the GitHub repo**

```bash
cd ~/Documents/Github/org-health
gh repo create RogoLabs/org-health --public --source=. --push --description "RogoLabs GitHub Actions health dashboard"
```

- [ ] **Step 2: Enable GitHub Pages**

```bash
gh api -X POST /repos/RogoLabs/org-health/pages -f build_type=legacy -f source='{"branch":"main","path":"/docs"}' 2>&1 || echo "Pages may need manual setup"
```

- [ ] **Step 3: Add the ORG_ADMIN_TOKEN secret**

```bash
gh secret set ORG_ADMIN_TOKEN --repo RogoLabs/org-health
```

(This will prompt for the token value — use a PAT with `admin:org` scope)

- [ ] **Step 4: Trigger initial workflow run**

```bash
gh workflow run update.yml --repo RogoLabs/org-health
```

- [ ] **Step 5: Verify the Pages site is live**

```bash
gh api /repos/RogoLabs/org-health/pages --jq '.html_url'
```

Expected: `https://rogolabs.github.io/org-health/`
