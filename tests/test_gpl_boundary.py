"""Guard: the orchestration backend must never import CLIMADA (GPL-3.0 boundary).

CLIMADA / climada_petals are GPL-3.0. The backend (``src/climaterisk``) is pip-installed,
imports no CLIMADA, and talks to the worker only via the JSON file contract. All CLIMADA
use lives in ``worker/climaterisk_worker`` (a separate conda env). This test fails if any
module under ``src/`` adds a ``climada`` import — keeping the boundary enforceable in CI.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
_IMPORT = re.compile(r"^\s*(?:from|import)\s+climada(?:_petals)?\b", re.MULTILINE)


def test_backend_never_imports_climada() -> None:
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _IMPORT.search(text):
            offenders.append(str(py.relative_to(SRC.parent)))
    assert not offenders, (
        "GPL boundary violated — these backend files import CLIMADA (move to worker/): "
        + ", ".join(offenders)
    )
