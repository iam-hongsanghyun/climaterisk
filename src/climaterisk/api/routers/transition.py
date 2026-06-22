"""Transition-risk route — synchronous carbon-cost computation (no worker needed)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from climaterisk.api.deps import get_session_store
from climaterisk.data.session_store import SessionStore
from climaterisk.transition.carbon import TransitionResult, compute_transition_risk

router = APIRouter(prefix="/session", tags=["transition"])

StoreDep = Annotated[SessionStore, Depends(get_session_store)]


@router.post("/{session_id}/transition", response_model=TransitionResult)
def run_transition(session_id: str, store: StoreDep) -> TransitionResult:
    """Compute the portfolio's transition (carbon-cost) risk under its NGFS scenario."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return compute_transition_risk(portfolio)
