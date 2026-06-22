"""Submit runs to the CLIMADA worker subprocess and poll for completion.

MVP mechanism (single-node, local-first): write ``request.json``, spawn the
climada-env python running ``climaterisk_worker.run_job <run_dir>`` non-blocking,
and on poll read ``result.json`` once the process exits. No broker required. Handles
both impact runs and cost-benefit runs (distinguished by the request ``mode``).
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from climaterisk.config import Settings
from climaterisk.core.entities import Portfolio
from climaterisk.engines.base import (
    CostBenefitRequest,
    IngestRequest,
    LitPopRequest,
    MeasureSpec,
    PhysicalRunRequest,
    UncertaintyRequest,
)
from climaterisk.logger import get_logger
from climaterisk.runs.store import Run, RunStore

logger = get_logger(__name__)


class RunManager:
    """Orchestrate physical-risk and cost-benefit runs against the external CLIMADA worker."""

    def __init__(self, settings: Settings, store: RunStore) -> None:
        self._settings = settings
        self._store = store
        self._procs: dict[str, subprocess.Popen[bytes]] = {}

    def _spawn(self, run_id: str, run_dir: Path, request_json: str) -> None:
        """Write the request and spawn the worker subprocess (non-blocking)."""
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "request.json").write_text(request_json, encoding="utf-8")
        python = self._settings.resolve_worker_python()
        cmd = [python, "-m", self._settings.worker_module, str(run_dir)]
        # Inject the backend-resolved hazard-catalog dir so the worker resolves the
        # same single location (it never imports the backend config; GPL boundary).
        env = {
            **os.environ,
            "MPLBACKEND": "Agg",
            "CLIMATERISK_HAZARD_DB": str(self._settings.hazard_db_path),
        }
        log = (run_dir / "worker.log").open("wb")
        logger.info("run %s: spawning worker (%s)", run_id, python)
        proc = subprocess.Popen(
            cmd, cwd=str(self._settings.worker_dir), stdout=log, stderr=subprocess.STDOUT, env=env
        )
        self._procs[run_id] = proc
        self._store.update(run_id, "running")

    def submit(self, portfolio: Portfolio) -> Run:
        """Create a physical-risk run and spawn its worker."""
        run_id = uuid.uuid4().hex
        perils = [p.value for p in portfolio.run_config.perils]
        run = self._store.create(run_id, portfolio.id, portfolio.scenario.climate, perils)
        request = PhysicalRunRequest.from_portfolio(portfolio)
        self._spawn(run_id, self._settings.runs_path / run_id, request.model_dump_json(indent=2))
        run.status = "running"
        return run

    def submit_cost_benefit(self, portfolio: Portfolio, measures: list[MeasureSpec]) -> Run:
        """Create an adaptation cost-benefit run and spawn its worker."""
        run_id = uuid.uuid4().hex
        run = self._store.create(run_id, portfolio.id, portfolio.scenario.climate, ["cost_benefit"])
        request = CostBenefitRequest.from_portfolio(portfolio, measures)
        self._spawn(run_id, self._settings.runs_path / run_id, request.model_dump_json(indent=2))
        run.status = "running"
        return run

    def submit_uncertainty(self, portfolio: Portfolio, n_samples: int = 50) -> Run:
        """Create a Monte-Carlo uncertainty run and spawn its worker."""
        run_id = uuid.uuid4().hex
        run = self._store.create(run_id, portfolio.id, portfolio.scenario.climate, ["uncertainty"])
        request = UncertaintyRequest.from_portfolio(portfolio, n_samples)
        self._spawn(run_id, self._settings.runs_path / run_id, request.model_dump_json(indent=2))
        run.status = "running"
        return run

    def submit_litpop(self, portfolio: Portfolio, country: str) -> Run:
        """Create a LitPop modeled-exposure run and spawn its worker."""
        run_id = uuid.uuid4().hex
        run = self._store.create(run_id, portfolio.id, portfolio.scenario.climate, ["litpop"])
        request = LitPopRequest.from_portfolio(portfolio, country)
        self._spawn(run_id, self._settings.runs_path / run_id, request.model_dump_json(indent=2))
        run.status = "running"
        return run

    def submit_ingest(
        self, portfolio: Portfolio, source: str, peril: str, scenario: str, year: int
    ) -> Run:
        """Create a data-ingest run (download + refine a source into the local catalog)."""
        run_id = uuid.uuid4().hex
        run = self._store.create(run_id, portfolio.id, scenario, [f"ingest:{source}"])
        request = IngestRequest.from_portfolio(portfolio, source, peril, scenario, year)
        self._spawn(run_id, self._settings.runs_path / run_id, request.model_dump_json(indent=2))
        run.status = "running"
        return run

    def poll(self, run_id: str) -> Run | None:
        """Return the current run, finalizing it if its worker has exited."""
        run = self._store.get(run_id)
        if run is None:
            return None
        if run.status in ("done", "error"):
            return run

        proc = self._procs.get(run_id)
        run_dir = self._settings.runs_path / run_id
        result_path = run_dir / "result.json"

        if proc is None:  # backend restarted: fall back to the result file
            return self._finalize(run_id, run_dir) if result_path.is_file() else run
        if proc.poll() is None:
            return run  # still running
        self._procs.pop(run_id, None)
        return self._finalize(run_id, run_dir)

    def _finalize(self, run_id: str, run_dir: Path) -> Run | None:
        """Read the worker's result.json (any output shape) and store it."""
        result_path = run_dir / "result.json"
        if not result_path.is_file():
            self._store.update(run_id, "error", detail=f"no result.json. {self._log_tail(run_dir)}")
            return self._store.get(run_id)
        try:
            output = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._store.update(run_id, "error", detail=f"unreadable result.json: {exc}")
            return self._store.get(run_id)
        self._store.update(run_id, "done", output=output, detail=output.get("detail"))
        logger.info("run %s: done status=%s", run_id, output.get("status"))
        return self._store.get(run_id)

    @staticmethod
    def _log_tail(run_dir: Path, n: int = 800) -> str:
        log = run_dir / "worker.log"
        if not log.is_file():
            return ""
        return f"worker.log tail: …{log.read_text(encoding='utf-8', errors='replace')[-n:]}"
