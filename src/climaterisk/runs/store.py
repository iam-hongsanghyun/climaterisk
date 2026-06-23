"""SQLite-backed store for analysis runs (the ``runs`` table in ``app.db``)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

RunStatus = str  # "queued" | "running" | "done" | "error"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Run(BaseModel):
    """A submitted physical-risk run and (once finished) its engine output."""

    id: str
    session_id: str
    status: RunStatus
    climate_scenario: str
    perils: list[str]
    created_at: str
    updated_at: str
    output: dict[str, Any] | None = None  # PhysicalRunOutput as a plain dict
    detail: str | None = None


class RunStore:
    """Persist and update analysis-run rows."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id               TEXT PRIMARY KEY,
                    session_id       TEXT NOT NULL,
                    status           TEXT NOT NULL,
                    climate_scenario TEXT NOT NULL,
                    perils_json      TEXT NOT NULL,
                    output_json      TEXT,
                    detail           TEXT,
                    created_at       TEXT NOT NULL,
                    updated_at       TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            session_id=row["session_id"],
            status=row["status"],
            climate_scenario=row["climate_scenario"],
            perils=json.loads(row["perils_json"]),
            output=json.loads(row["output_json"]) if row["output_json"] else None,
            detail=row["detail"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(self, run_id: str, session_id: str, climate_scenario: str, perils: list[str]) -> Run:
        ts = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO runs
                   (id, session_id, status, climate_scenario, perils_json, created_at, updated_at)
                   VALUES (?, ?, 'queued', ?, ?, ?, ?)""",
                (run_id, session_id, climate_scenario, json.dumps(perils), ts, ts),
            )
        return Run(
            id=run_id,
            session_id=session_id,
            status="queued",
            climate_scenario=climate_scenario,
            perils=perils,
            created_at=ts,
            updated_at=ts,
        )

    def get(self, run_id: str) -> Run | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def fail_stale_runs(self, detail: str) -> int:
        """Mark any run still ``queued``/``running`` as ``error`` (called on backend start).

        Their worker subprocesses were children of a previous backend process and are gone,
        so without this they would be polled as "running" forever. Returns the count failed.
        """
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE runs SET status = 'error', detail = ?, updated_at = ? "
                "WHERE status IN ('queued', 'running')",
                (detail, _now_iso()),
            )
            return int(cur.rowcount)

    def update(
        self,
        run_id: str,
        status: RunStatus,
        output: dict[str, Any] | None = None,
        detail: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, output_json = ?, detail = ?, updated_at = ? "
                "WHERE id = ?",
                (
                    status,
                    json.dumps(output) if output is not None else None,
                    detail,
                    _now_iso(),
                    run_id,
                ),
            )
