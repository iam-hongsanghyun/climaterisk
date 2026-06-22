"""Unit tests for the SQLite session store."""

from __future__ import annotations

from pathlib import Path

from climaterisk.core.entities import Asset
from climaterisk.data.session_store import SessionStore


def test_create_get_save_delete(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "app.db")

    portfolio = store.create()
    assert store.get(portfolio.id) is not None
    assert store.get(portfolio.id).assets == []  # type: ignore[union-attr]

    portfolio.assets.append(Asset(name="A", lat=1.0, lon=2.0))
    saved = store.save(portfolio.id, portfolio)
    assert saved is not None
    assert len(store.get(portfolio.id).assets) == 1  # type: ignore[union-attr]

    assert store.delete(portfolio.id) is True
    assert store.get(portfolio.id) is None
    assert store.delete(portfolio.id) is False


def test_save_unknown_session_returns_none(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "app.db")
    portfolio = store.create()
    portfolio.id = "does-not-exist"
    assert store.save("does-not-exist", portfolio) is None
