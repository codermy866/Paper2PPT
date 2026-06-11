from __future__ import annotations

import time

import pytest

httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from api_server import TASKS, TASK_LOCK, _persist_task, app
from task_store import TaskStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "tasks.db"
    inputs = tmp_path / "inputs"
    outputs = tmp_path / "outputs"
    inputs.mkdir()
    outputs.mkdir()
    monkeypatch.setattr("api_server.INPUTS_DIR", inputs)
    monkeypatch.setattr("api_server.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("config.INPUTS_DIR", inputs)
    monkeypatch.setattr("config.OUTPUTS_DIR", outputs)
    monkeypatch.setattr("pipeline.OUTPUTS_DIR", outputs)
    store = TaskStore(db_path=db)
    monkeypatch.setattr("api_server.STORE", store)
    monkeypatch.setattr(
        "api_server.PIPELINE",
        __import__("pipeline").TaskPipeline(
            store=store,
            on_update=lambda tid, upd: _persist_task(tid, upd),
        ),
    )
    with TASK_LOCK:
        TASKS.clear()
    with TestClient(app) as test_client:
        yield test_client


def _run_task_to_completion(client: TestClient, task_id: str) -> dict:
    final = None
    for _ in range(120):
        payload = client.get(f"/api/tasks/{task_id}").json()
        if payload["status"] == "waiting_confirmation":
            client.post(
                f"/api/tasks/{task_id}/confirm",
                json={"action": "approve", "feedback": ""},
            )
        elif payload["status"] in {"succeeded", "failed"}:
            final = payload
            break
        time.sleep(0.2)
    assert final is not None
    return final


def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_example_task_and_poll(client: TestClient):
    resp = client.post(
        "/api/tasks",
        data={
            "input_mode": "example",
            "page_count": "6",
            "template_id": "tech-sharing",
            "style_id": "blue",
            "instruction": "highlight results",
        },
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    final = _run_task_to_completion(client, task_id)
    assert final["status"] == "succeeded"
    assert final["result"]["html_preview_url"].endswith("index.html")
    assert final["result"]["applied_config"]["style_id"] == "blue"


def test_upload_markdown_task_uses_text_parser(client: TestClient):
    resp = client.post(
        "/api/tasks",
        data={
            "input_mode": "upload",
            "page_count": "6",
            "template_id": "tech-sharing",
            "style_id": "blue",
        },
        files={
            "file": (
                "paper.md",
                b"# Markdown Paper\n\n## Abstract\n\nThis paper studies markdown input for Paper2PPT.\n\n## Method\n\nWe parse it as text.",
                "text/markdown",
            )
        },
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    payload = client.get(f"/api/tasks/{task_id}").json()
    assert payload["config"]["source_kind"] == "text"
    assert payload["config"]["source_path"].endswith(".md")


def test_batch_eval_endpoint(client: TestClient):
    resp = client.post("/api/eval/batch")
    assert resp.status_code == 200
    report = resp.json()
    assert report["passed"] is True
    assert report["case_count"] >= 3


def test_logs_and_versions(client: TestClient):
    resp = client.post(
        "/api/tasks",
        data={"input_mode": "example", "page_count": "6", "template_id": "tech-sharing", "style_id": "green"},
    )
    task_id = resp.json()["task_id"]
    _run_task_to_completion(client, task_id)

    logs_resp = client.get(f"/api/tasks/{task_id}/logs")
    assert logs_resp.status_code == 200
    assert len(logs_resp.json()["logs"]) >= 1

    versions_resp = client.get(f"/api/tasks/{task_id}/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()["versions"]
    assert len(versions) >= 1

    version_no = versions[0]["version_no"]
    detail_resp = client.get(f"/api/tasks/{task_id}/versions/{version_no}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["snapshot"]["result"]["title"]

    restore_resp = client.post(f"/api/tasks/{task_id}/versions/{version_no}/restore")
    assert restore_resp.status_code == 200
    assert restore_resp.json()["result"]["title"]
