"""Session routes — create / read / update (full-model sync) / delete.

The frontend persists only the session id and PUTs the whole portfolio document
on a debounce. This mirrors the backend-owns-the-model pattern.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from climaterisk.api.deps import get_session_store
from climaterisk.core.entities import Portfolio
from climaterisk.data.session_store import SessionStore

router = APIRouter(prefix="/session", tags=["session"])

StoreDep = Annotated[SessionStore, Depends(get_session_store)]


@router.post("", response_model=Portfolio, status_code=status.HTTP_201_CREATED)
def create_session(store: StoreDep) -> Portfolio:
    """Create a fresh, empty session and return its portfolio (id == session id)."""
    return store.create()


@router.get("/{session_id}", response_model=Portfolio)
def get_session(session_id: str, store: StoreDep) -> Portfolio:
    """Return the portfolio for a session, or 404 if unknown."""
    portfolio = store.get(session_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return portfolio


@router.put("/{session_id}", response_model=Portfolio)
def save_session(session_id: str, portfolio: Portfolio, store: StoreDep) -> Portfolio:
    """Replace the stored model for a session (full-model sync). 404 if unknown."""
    # The path id is authoritative; keep the document id aligned with the session.
    portfolio.id = session_id
    saved = store.save(session_id, portfolio)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return saved


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, store: StoreDep) -> Response:
    """Delete a session. 404 if it did not exist."""
    if not store.delete(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
