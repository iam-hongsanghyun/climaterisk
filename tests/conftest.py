"""Test fixtures — isolate runtime data into a temp dir and build a fresh app."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _isolate_data(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point the data dir at a temp location and clear cached singletons.

    No-op when the backend package is not importable (e.g. the CLIMADA worker env
    running the engine regression test) — there is no backend data dir to isolate.
    """
    try:
        from climaterisk.api.deps import get_session_store
        from climaterisk.config import get_settings
        from climaterisk.data.libraries import load_libraries
    except ModuleNotFoundError:
        yield
        return

    data_dir = tmp_path_factory.mktemp("climaterisk-data")
    os.environ["CLIMATERISK_DATA_DIR"] = str(data_dir)
    get_settings.cache_clear()
    get_session_store.cache_clear()
    load_libraries.cache_clear()
    yield


@pytest.fixture
def client(_isolate_data: None) -> TestClient:
    """A TestClient backed by a freshly built app (after data isolation).

    Imports are local so this conftest stays importable in the CLIMADA worker env
    (which has no FastAPI/backend deps) when running the engine regression test.
    """
    from fastapi.testclient import TestClient

    from climaterisk.api.main import create_app

    return TestClient(create_app())
