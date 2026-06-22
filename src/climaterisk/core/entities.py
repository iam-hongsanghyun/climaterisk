"""Domain entities — the backend-owned model, serialized per session.

The ``Portfolio`` is the canonical session document: the frontend persists only a
session id and syncs this whole document back via PUT (debounced). All numeric
inputs that the physical/transition engines consume originate here.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from climaterisk.core.enums import (
    ClimateScenario,
    DepthLevel,
    GeographicScale,
    Peril,
    Sector,
    TransitionScenario,
)


def _new_id() -> str:
    return uuid.uuid4().hex


class Asset(BaseModel):
    """A located facility — one CLIMADA exposure point (or footprint)."""

    id: str = Field(default_factory=_new_id)
    name: str = "Untitled asset"
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    sector: Sector = Sector.REAL_ESTATE
    geographic_scale: GeographicScale = GeographicScale.POINT
    value: float = Field(default=0.0, ge=0.0, description="Asset value at risk, in `currency`.")
    currency: str = "USD"
    annual_emissions_tco2e: float | None = Field(
        default=None, ge=0.0, description="Scope-1 emissions; if None, proxied from sector factors."
    )
    vulnerability_class: str | None = Field(
        default=None,
        description="Vulnerability-class id (peril-agnostic); if None, the sector default is used.",
    )
    properties: dict[str, float | str | bool] = Field(default_factory=dict)


class Scenario(BaseModel):
    """The scenario context a run is evaluated under."""

    climate: ClimateScenario = ClimateScenario.RCP45
    transition: TransitionScenario = TransitionScenario.NET_ZERO_2050
    anchor_years: list[int] = Field(default_factory=lambda: [2030, 2040, 2050])


class RunConfig(BaseModel):
    """Run-time options for an analysis."""

    perils: list[Peril] = Field(default_factory=lambda: [Peril.TROPICAL_CYCLONE])
    discount_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    options: dict[str, float | str | bool] = Field(default_factory=dict)


class VulnerabilityOverride(BaseModel):
    """User edits to a vulnerability class (impact-function studio). Unset fields fall
    back to the bundled library values."""

    tc_v_half: float | None = Field(default=None, gt=0.0)
    wf_max_mdd: float | None = Field(default=None, ge=0.0, le=1.0)
    flood_mdr: list[float] | None = None


class Portfolio(BaseModel):
    """The session model — a named set of assets plus its scenario + run config."""

    id: str = Field(default_factory=_new_id)
    name: str = "Untitled portfolio"
    depth_level: DepthLevel = DepthLevel.ASSET
    assets: list[Asset] = Field(default_factory=list)
    scenario: Scenario = Field(default_factory=Scenario)
    run_config: RunConfig = Field(default_factory=RunConfig)
    # Impact-function studio: per-class curve overrides (class id -> override).
    vulnerability_overrides: dict[str, VulnerabilityOverride] = Field(default_factory=dict)

    @classmethod
    def empty(cls) -> Portfolio:
        """Create a fresh, empty portfolio (used when a new session is created)."""
        return cls()
