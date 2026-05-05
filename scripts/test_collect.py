import json
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import collect


def test_fetch_repos_returns_list_of_names():
    repos_page1 = [
        {"name": "repo-a", "visibility": "public"},
        {"name": "repo-b", "visibility": "public"},
    ]

    with patch("collect.api_get", side_effect=[repos_page1, []]):
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
