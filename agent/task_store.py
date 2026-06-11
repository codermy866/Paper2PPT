from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import TASK_DB_PATH, ensure_runtime_dirs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, db_path: Path = TASK_DB_PATH) -> None:
        ensure_runtime_dirs()
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS task_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS task_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        version_no INTEGER NOT NULL,
                        label TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        snapshot TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(task_id, version_no)
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def save_task(self, task_id: str, payload: Dict[str, Any]) -> None:
        now = _now_iso()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO tasks(task_id, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        payload=excluded.payload,
                        updated_at=excluded.updated_at
                    """,
                    (task_id, json.dumps(payload, ensure_ascii=False), now, now),
                )
                conn.commit()
            finally:
                conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if not row:
                    return None
                return json.loads(row["payload"])
            finally:
                conn.close()

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT payload FROM tasks ORDER BY updated_at DESC"
                ).fetchall()
                return [json.loads(row["payload"]) for row in rows]
            finally:
                conn.close()

    def append_log(self, task_id: str, message: str, level: str = "info") -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO task_logs(task_id, level, message, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (task_id, level, message, _now_iso()),
                )
                conn.commit()
            finally:
                conn.close()

    def list_logs(self, task_id: str, limit: int = 200) -> List[Dict[str, str]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT level, message, created_at
                    FROM task_logs
                    WHERE task_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (task_id, limit),
                ).fetchall()
                return [
                    {
                        "level": row["level"],
                        "message": row["message"],
                        "created_at": row["created_at"],
                    }
                    for row in reversed(rows)
                ]
            finally:
                conn.close()

    def add_version(
        self,
        task_id: str,
        label: str,
        summary: str,
        snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_no), 0) AS max_v FROM task_versions WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
                version_no = int(row["max_v"]) + 1
                created_at = _now_iso()
                conn.execute(
                    """
                    INSERT INTO task_versions(task_id, version_no, label, summary, snapshot, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        version_no,
                        label,
                        summary,
                        json.dumps(snapshot, ensure_ascii=False),
                        created_at,
                    ),
                )
                conn.commit()
                return {
                    "version_no": version_no,
                    "label": label,
                    "summary": summary,
                    "created_at": created_at,
                }
            finally:
                conn.close()

    def list_versions(self, task_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT version_no, label, summary, created_at
                    FROM task_versions
                    WHERE task_id = ?
                    ORDER BY version_no DESC
                    """,
                    (task_id,),
                ).fetchall()
                return [
                    {
                        "version_no": row["version_no"],
                        "label": f"v{row['version_no']}",
                        "summary": row["summary"],
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ]
            finally:
                conn.close()

    def get_version(self, task_id: str, version_no: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT version_no, label, summary, snapshot, created_at
                    FROM task_versions
                    WHERE task_id = ? AND version_no = ?
                    """,
                    (task_id, version_no),
                ).fetchone()
                if not row:
                    return None
                return {
                    "version_no": row["version_no"],
                    "label": row["label"],
                    "summary": row["summary"],
                    "snapshot": json.loads(row["snapshot"]),
                    "created_at": row["created_at"],
                }
            finally:
                conn.close()

    def load_tasks_into_memory(self) -> Dict[str, Dict[str, Any]]:
        tasks: Dict[str, Dict[str, Any]] = {}
        for payload in self.list_tasks():
            task_id = payload.get("task_id")
            if task_id:
                tasks[task_id] = payload
        return tasks
