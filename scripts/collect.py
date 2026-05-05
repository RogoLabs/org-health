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
