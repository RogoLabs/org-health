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


if __name__ == "__main__":
    main()
