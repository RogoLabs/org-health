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
