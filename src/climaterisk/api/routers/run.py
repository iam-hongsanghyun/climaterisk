"""Run routes — submit a physical-risk analysis and poll for results.

POST submits a run (spawns the CLIMADA worker); GET polls until it is done/error.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from climaterisk.api.deps import get_run_manager, get_session_store
from climaterisk.data.session_store import SessionStore
from climaterisk.engines.base import MeasureSpec
from climaterisk.runs.manager import RunManager
from climaterisk.runs.store import Run

router = APIRouter(prefix="/session", tags=["run"])

StoreDep = Annotated[SessionStore, Depends(get_session_store)]
ManagerDep = Annotated[RunManager, Depends(get_run_manager)]


@router.post("/{session_id}/run", response_model=Run)
def submit_run(session_id: str, store: StoreDep, manager: ManagerDep) -> Run:
    """Submit an analysis run for the session's portfolio."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    if not portfolio.run_config.perils:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no perils selected")
    return manager.submit(portfolio)


@router.post("/{session_id}/cost-benefit", response_model=Run)
def submit_cost_benefit(
    session_id: str, measures: list[MeasureSpec], store: StoreDep, manager: ManagerDep
) -> Run:
    """Submit an adaptation cost-benefit run (polled via the run-status route)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    if not measures:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no adaptation measures provided")
    return manager.submit_cost_benefit(portfolio, measures)


@router.post("/{session_id}/uncertainty", response_model=Run)
def submit_uncertainty(
    session_id: str, store: StoreDep, manager: ManagerDep, n_samples: int = 50
) -> Run:
    """Submit a Monte-Carlo uncertainty run (polled via the run-status route)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    return manager.submit_uncertainty(portfolio, max(10, min(n_samples, 200)))


@router.post("/{session_id}/litpop", response_model=Run)
def submit_litpop(session_id: str, country: str, store: StoreDep, manager: ManagerDep) -> Run:
    """Submit a LitPop modeled-exposure run for a country (polled via run-status)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not country or len(country) != 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="country must be an ISO3 code")
    return manager.submit_litpop(portfolio, country.upper())


@router.post("/{session_id}/forecast", response_model=Run)
def submit_forecast(session_id: str, store: StoreDep, manager: ManagerDep) -> Run:
    """Submit an operational TC-forecast run (latest ECMWF ensemble tracks)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    return manager.submit_forecast(portfolio)


@router.post("/{session_id}/calibration", response_model=Run)
def submit_calibration(session_id: str, store: StoreDep, manager: ManagerDep) -> Run:
    """Submit an impact-function calibration run (fit TC v_half to EM-DAT observed losses)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    return manager.submit_calibration(portfolio)


@router.post("/{session_id}/supplychain", response_model=Run)
def submit_supplychain(
    session_id: str,
    store: StoreDep,
    manager: ManagerDep,
    mriot_type: str = "WIOD16",
    mriot_year: int = 2010,
) -> Run:
    """Submit a supply-chain indirect-impact run (polled via the run-status route)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if not portfolio.assets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="portfolio has no assets")
    return manager.submit_supplychain(portfolio, mriot_type, mriot_year)


class IngestBody(BaseModel):
    """Request body for a data-ingest run (scenario/year default to the session)."""

    source: str  # "dataapi" | "aqueduct"
    peril: str = "river_flood"  # dataapi: tropical_cyclone | river_flood | wildfire | earthquake
    scenario: str | None = None
    year: int | None = None


@router.post("/{session_id}/ingest", response_model=Run)
def submit_ingest(session_id: str, body: IngestBody, store: StoreDep, manager: ManagerDep) -> Run:
    """Download + refine a data source into the local CLIMADA catalog (polled via run-status).

    Scoped to the session's assets: the worker bounds the download to their bbox and
    keys the catalog entry to their region, so the matching runner picks it up.
    """
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    if body.source not in ("dataapi", "aqueduct"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"unknown source '{body.source}'")
    if not portfolio.assets:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="place at least one asset first — ingestion is scoped to the portfolio region",
        )
    scenario = body.scenario or portfolio.scenario.climate
    anchor = portfolio.scenario.anchor_years
    year = body.year or (max(anchor) if anchor else 2050)
    return manager.submit_ingest(portfolio, body.source, body.peril, scenario, year)


@router.get("/{session_id}/run/{run_id}", response_model=Run)
def get_run(session_id: str, run_id: str, manager: ManagerDep) -> Run:
    """Poll a run; finalizes it once the worker subprocess has exited."""
    run = manager.poll(run_id)
    if run is None or run.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="run not found")
    return run
