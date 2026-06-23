"""Worker-pool capacity guard (offline, hermetic — no real subprocess spawned).

Locks in the fix for the regression where a too-tight max_workers 503'd legitimate
runs: finished workers must free their slot, and only at the ceiling does _spawn raise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from climaterisk.config import Settings
from climaterisk.runs.manager import RunManager, WorkerCapacityError
from climaterisk.runs.store import RunStore


class _FakeProc:
    """Stand-in for subprocess.Popen: poll() returns None while 'running', else exit code."""

    def __init__(self, running: bool) -> None:
        self._running = running

    def poll(self) -> int | None:
        return None if self._running else 0


def _manager(tmp_path: Path, max_workers: int) -> RunManager:
    settings = Settings(data_dir=tmp_path, max_workers=max_workers)
    return RunManager(settings, RunStore(tmp_path / "runs.db"))


def test_finished_workers_do_not_occupy_slots(tmp_path: Path) -> None:
    mgr = _manager(tmp_path, max_workers=2)
    mgr._procs = {"a": _FakeProc(False), "b": _FakeProc(False)}  # type: ignore[dict-item]
    assert mgr._active_count() == 0


def test_spawn_raises_at_capacity(tmp_path: Path) -> None:
    mgr = _manager(tmp_path, max_workers=2)
    mgr._procs = {"a": _FakeProc(True), "b": _FakeProc(True)}  # type: ignore[dict-item]
    # The capacity check runs before any Popen, so this is hermetic.
    with pytest.raises(WorkerCapacityError):
        mgr._spawn("c", tmp_path / "c", "{}")


def test_default_ceiling_is_generous() -> None:
    # Guard against regressing back to a too-tight cap that blocked normal multi-engine use.
    assert Settings().max_workers >= 6
