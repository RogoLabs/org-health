import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
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


def collect_billing(org):
    url = f"{BASE_URL}/organizations/{org}/settings/billing/usage"
    data = api_get(url)

    minutes = {}
    storage = {}

    for item in data.get("usageItems", []):
        if item["product"] != "actions":
            continue
        repo = item["repositoryName"]
        month = item["date"][:7]

        if item["unitType"] == "Minutes":
            minutes.setdefault(repo, {})[month] = item["quantity"]
        elif item["unitType"] == "GigabyteHours":
            storage.setdefault(repo, {})[month] = item["quantity"]

    return {"minutes": minutes, "storage": storage}


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

    durations = collect_durations(ORG, repos)
    write_json(OUTPUT_DIR, "durations.json", durations)
    print(f"Durations: {len(durations)} repos with timing data")

    failures, contention = collect_failures_and_contention(ORG, repos)
    write_json(OUTPUT_DIR, "failures.json", failures)
    write_json(OUTPUT_DIR, "contention.json", contention)
    print(f"Failures: {len(failures)} recent, {len(contention)} contention events")


if __name__ == "__main__":
    main()
