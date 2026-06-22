"""Shared API dependencies (process-wide singletons)."""

from __future__ import annotations

from functools import lru_cache

from climaterisk.config import get_settings
from climaterisk.data.session_store import SessionStore
from climaterisk.runs.manager import RunManager
from climaterisk.runs.store import RunStore


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    """Return the singleton :class:`SessionStore` backed by ``data/app.db``."""
    return SessionStore(get_settings().data_path / "app.db")


@lru_cache(maxsize=1)
def get_run_store() -> RunStore:
    """Return the singleton :class:`RunStore` backed by ``data/app.db``."""
    return RunStore(get_settings().data_path / "app.db")


@lru_cache(maxsize=1)
def get_run_manager() -> RunManager:
    """Return the singleton :class:`RunManager` (tracks live worker subprocesses)."""
    return RunManager(get_settings(), get_run_store())
