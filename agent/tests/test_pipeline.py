from __future__ import annotations

from pipeline import TaskPipeline
from task_store import TaskStore


def test_pipeline_confirmation_flow(tmp_path):
    db = tmp_path / "tasks.db"
    store = TaskStore(db_path=db)
    updates_log: list[tuple[str, dict]] = []

    def on_update(task_id: str, updates: dict) -> None:
        task = store.get_task(task_id) or {"task_id": task_id}
        task.update(updates)
        store.save_task(task_id, task)
        updates_log.append((task_id, updates))

    pipeline = TaskPipeline(store=store, on_update=on_update)
    task_id = "confirm-flow"
    store.save_task(
        task_id,
        {
            "task_id": task_id,
            "status": "queued",
            "message": "queued",
            "completed_steps": 0,
            "total_steps": 6,
            "current_stage": "parse",
            "timeline": [],
            "config": {
                "input_mode": "example",
                "page_count": 6,
                "template_id": "tech-sharing",
                "style_id": "blue",
                "instruction": "",
                "llm_provider": "local",
                "source_path": str(
                    __import__("pathlib").Path(__file__).resolve().parent.parent / "sample_data" / "sample_paper.txt"
                ),
            },
        },
    )

    pipeline.run_until_pause_or_done(task_id)
    task = store.get_task(task_id)
    assert task["status"] == "waiting_confirmation"
    assert task["current_stage"] == "outline_confirm"

    # Approve every confirmation stage the pipeline pauses on
    # (outline_confirm, slides_confirm, layout_confirm).
    for _ in range(5):
        task = store.get_task(task_id)
        if task["status"] != "waiting_confirmation":
            break
        pipeline.continue_after_confirm(task_id, "approve", "")

    task = store.get_task(task_id)
    assert task["status"] == "succeeded"
    assert task["result"]["html_download_url"].endswith("/html/download")
    versions = store.list_versions(task_id)
    assert len(versions) >= 1


def test_confirmation_items_include_all_requested_slides(tmp_path):
    db = tmp_path / "tasks.db"
    store = TaskStore(db_path=db)

    def on_update(task_id: str, updates: dict) -> None:
        task = store.get_task(task_id) or {"task_id": task_id}
        task.update(updates)
        store.save_task(task_id, task)

    pipeline = TaskPipeline(store=store, on_update=on_update)
    task_id = "confirm-all-slides"
    page_count = 13
    store.save_task(
        task_id,
        {
            "task_id": task_id,
            "status": "queued",
            "message": "queued",
            "completed_steps": 0,
            "total_steps": 8,
            "current_stage": "parse",
            "timeline": [],
            "config": {
                "input_mode": "example",
                "page_count": page_count,
                "template_id": "tech-sharing",
                "style_id": "blue",
                "instruction": "",
                "llm_provider": "local",
                "source_path": str(
                    __import__("pathlib").Path(__file__).resolve().parent.parent / "sample_data" / "sample_paper.txt"
                ),
            },
        },
    )

    pipeline.run_until_pause_or_done(task_id)
    pipeline.continue_after_confirm(task_id, "approve", "")
    task = store.get_task(task_id)
    assert task["current_stage"] == "slides_confirm"
    assert len(task["pending_confirmation"]["items"]) == page_count

    pipeline.continue_after_confirm(task_id, "approve", "")
    task = store.get_task(task_id)
    assert task["current_stage"] == "layout_confirm"
    assert len(task["pending_confirmation"]["items"]) == page_count
