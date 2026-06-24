"""Asset financial models — the one sector-specific seam in the finance layer.

The finance engine (NPV/DSCR/rating/CRP in :mod:`core`) is sector-agnostic: it consumes a
*(baseline EBITDA, stressed EBITDA)* pair and never knows where the numbers came from. This
module produces that pair, and is the only place that varies by asset archetype:

* ``generic`` — every non-generation asset (real estate, factory, port, …): the stressed
  EBITDA is the baseline reduced by the expected annual climate loss (physical AAI + carbon).
  This reproduces the original CRP behaviour exactly.
* ``power_gen`` — a generation asset (power plant): EBITDA is built up from generation
  (``capacity × 8760 × CF × price − opex − carbon``) and the stressed run reduces the
  *effective capacity factor* through the operational channels in :mod:`channels`, then also
  subtracts the physical-damage AAI.

Adding a future archetype (crop yield, transport throughput) means a third function here —
nothing in :mod:`core` or the rest of the pipeline changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from climaterisk.finance import channels

GENERIC = "generic"
POWER_GEN = "power_gen"


@dataclass
class GenerationInputs:
    """Generation economics for a power plant (all per-year, asset currency)."""

    capacity_mw: float  # nameplate capacity (MW)
    power_price: float  # realised price per MWh
    capacity_factor: float  # baseline (no-stress) capacity factor in [0, 1]
    fixed_opex: float = 0.0  # annual fixed O&M
    opex_per_mwh: float = 0.0  # variable O&M per MWh generated


@dataclass
class ChannelMagnitudes:
    """Stressed-scenario channel fractions in [0, 1] (0 = channel inactive)."""

    dispatch_penalty: float = 0.0  # policy dispatch / capacity-factor reduction
    outage_rate: float = 0.0  # forced downtime (wildfire/storm)
    capacity_derate: float = 0.0  # drought/water cooling constraint
    efficiency_loss: float = 0.0  # heat-driven output derate
    water_constrained_cf: float | None = None  # hard CF cap under drought


@dataclass
class EbitdaPair:
    """Baseline vs climate-stressed annual EBITDA, plus a channel breakdown for display."""

    baseline: float
    stressed: float
    breakdown: dict[str, Any] = field(default_factory=dict)

    @property
    def climate_loss(self) -> float:
        """EBITDA removed by the climate/policy stress (baseline − stressed)."""
        return self.baseline - self.stressed


def generic_pair(annual_ebitda: float, annual_climate_loss: float) -> EbitdaPair:
    """Generic model: stressed EBITDA = baseline − expected annual climate loss."""
    loss = max(0.0, annual_climate_loss)
    return EbitdaPair(
        baseline=annual_ebitda,
        stressed=annual_ebitda - loss,
        breakdown={"model": GENERIC, "annual_climate_loss": loss},
    )


def power_gen_pair(
    gen: GenerationInputs,
    ch: ChannelMagnitudes,
    annual_aai: float = 0.0,
    carbon_cost: float = 0.0,
) -> EbitdaPair:
    """Power-generation model: build EBITDA from generation; stress the capacity factor.

    Baseline is the unstressed plant (CF_baseline, no carbon, no damage). The stressed run
    applies the operational channels to the capacity factor, then subtracts the transition
    carbon cost and the physical-damage AAI.

    Args:
        gen: generation economics (capacity, price, baseline CF, opex).
        ch: stressed-scenario channel magnitudes.
        annual_aai: expected annual physical damage (repair cost), asset currency.
        carbon_cost: annual transition carbon cost, asset currency.

    Returns:
        An :class:`EbitdaPair` with a breakdown of CFs, generation and revenue.
    """
    cf0 = channels.effective_capacity_factor(gen.capacity_factor)
    cf1 = channels.effective_capacity_factor(
        gen.capacity_factor,
        dispatch_penalty=ch.dispatch_penalty,
        outage_rate=ch.outage_rate,
        capacity_derate=ch.capacity_derate,
        efficiency_loss=ch.efficiency_loss,
        water_constrained_cf=ch.water_constrained_cf,
    )
    gen0 = gen.capacity_mw * channels.HOURS_PER_YEAR * cf0
    gen1 = gen.capacity_mw * channels.HOURS_PER_YEAR * cf1
    rev0 = gen0 * gen.power_price
    rev1 = gen1 * gen.power_price
    opex0 = gen.fixed_opex + gen.opex_per_mwh * gen0
    opex1 = gen.fixed_opex + gen.opex_per_mwh * gen1
    ebitda0 = rev0 - opex0
    ebitda1 = rev1 - opex1 - max(0.0, carbon_cost) - max(0.0, annual_aai)
    return EbitdaPair(
        baseline=ebitda0,
        stressed=ebitda1,
        breakdown={
            "model": POWER_GEN,
            "cf_baseline": cf0,
            "cf_effective": cf1,
            "generation_mwh_baseline": gen0,
            "generation_mwh_stressed": gen1,
            "revenue_baseline": rev0,
            "revenue_stressed": rev1,
            "carbon_cost": max(0.0, carbon_cost),
            "annual_aai": max(0.0, annual_aai),
            "channels": {
                "dispatch_penalty": ch.dispatch_penalty,
                "outage_rate": ch.outage_rate,
                "capacity_derate": ch.capacity_derate,
                "efficiency_loss": ch.efficiency_loss,
            },
        },
    )
