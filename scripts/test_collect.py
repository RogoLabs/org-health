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
