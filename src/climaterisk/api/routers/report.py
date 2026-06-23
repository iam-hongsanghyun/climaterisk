"""Report route — download a TCFD/ISSB-aligned HTML report for the portfolio."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from climaterisk.api.deps import get_run_store, get_session_store
from climaterisk.data.session_store import SessionStore
from climaterisk.report.html import build_html_report
from climaterisk.runs.store import RunStore
from climaterisk.transition.carbon import compute_transition_risk

router = APIRouter(prefix="/session", tags=["report"])

StoreDep = Annotated[SessionStore, Depends(get_session_store)]
RunStoreDep = Annotated[RunStore, Depends(get_run_store)]


@router.get("/{session_id}/report")
def download_report(
    session_id: str,
    store: StoreDep,
    runs: RunStoreDep,
    run_id: str | None = None,
    cb_run_id: str | None = None,
    unc_run_id: str | None = None,
    sc_run_id: str | None = None,
    fc_run_id: str | None = None,
    cal_run_id: str | None = None,
) -> HTMLResponse:
    """Return a self-contained HTML report (physical + transition, optional CB + uncertainty)."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")

    def _output_for(rid: str | None) -> dict[str, Any] | None:
        if not rid:
            return None
        r = runs.get(rid)
        return r.output if (r is not None and r.session_id == session_id) else None

    run = runs.get(run_id) if run_id else None
    if run is not None and run.session_id != session_id:
        run = None
    transition = compute_transition_risk(portfolio)

    html = build_html_report(
        portfolio,
        run,
        transition,
        cost_benefit=_output_for(cb_run_id),
        uncertainty=_output_for(unc_run_id),
        supplychain=_output_for(sc_run_id),
        forecast=_output_for(fc_run_id),
        calibration=_output_for(cal_run_id),
    )
    filename = f"climaterisk_report_{session_id[:8]}.html"
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
