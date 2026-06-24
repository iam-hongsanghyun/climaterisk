"""Operational risk channels for the power-generation financial model.

Pure functions (no I/O, no CLIMADA). Each channel reduces a thermal/renewable plant's
*effective capacity factor* — the fraction of nameplate energy it actually delivers — and
the channels compose multiplicatively. The reference parameters (outage λ / duration,
efficiency derate curve) live in ``finance_channels.json`` so every number is citable.

Algorithm:
    CF_eff = CF_base · (1 − d) · (1 − o) · (1 − c) · (1 − e)        [capped by water limit]
    where d = dispatch penalty (policy), o = outage rate (forced downtime),
          c = capacity/water derate (drought), e = efficiency loss (heat).
    outage_rate = f_event · (1 − e^(−λ·t_exp)) · t_dur / 8760
    efficiency_loss = max(0, T_ambient − T_design) · k_per_°C
ASCII: effective capacity factor is the baseline scaled down by each (1 − channel); outage
is event frequency times the per-event failure probability times duration share of the year.
"""

from __future__ import annotations

import math

HOURS_PER_YEAR = 8760.0


def _clamp01(x: float) -> float:
    """Clamp a fraction to the closed interval [0, 1]."""
    return max(0.0, min(1.0, x))


def outage_rate(
    event_freq_per_yr: float,
    failure_rate_per_hour: float,
    exposure_hours: float,
    outage_duration_hours: float,
) -> float:
    """Annual fraction of time the plant is forced offline by a hazard.

    Args:
        event_freq_per_yr: expected hazard events per year at the asset (1/yr).
        failure_rate_per_hour: per-hour failure hazard λ during exposure (1/h).
        exposure_hours: hours of exposure per event (h).
        outage_duration_hours: downtime per failure (h).

    Returns:
        Annual outage rate in [0, 1]: ``f · (1 − e^(−λ·t_exp)) · t_dur / 8760``.

    Algorithm:
        $$o = f \\cdot (1 - e^{-\\lambda t_{exp}}) \\cdot t_{dur} / 8760$$
        ASCII: outage = freq * (1 - exp(-lambda*exposure)) * duration / 8760.
    """
    if event_freq_per_yr <= 0 or failure_rate_per_hour <= 0:
        return 0.0
    p_fail = 1.0 - math.exp(-failure_rate_per_hour * max(0.0, exposure_hours))
    rate = event_freq_per_yr * p_fail * max(0.0, outage_duration_hours) / HOURS_PER_YEAR
    return _clamp01(rate)


def efficiency_loss(ambient_temp_c: float, design_temp_c: float, loss_per_degc: float) -> float:
    """Output/efficiency derate fraction from ambient temperature above the design point.

    Args:
        ambient_temp_c: representative ambient temperature (°C).
        design_temp_c: plant design / ISO ambient temperature (°C).
        loss_per_degc: fractional output loss per °C above design (1/°C).

    Returns:
        Efficiency loss fraction in [0, 1]: ``max(0, T − T_design) · k`` (no gain below design).
    """
    excess = max(0.0, ambient_temp_c - design_temp_c)
    return _clamp01(excess * max(0.0, loss_per_degc))


def effective_capacity_factor(
    cf_baseline: float,
    dispatch_penalty: float = 0.0,
    outage_rate: float = 0.0,
    capacity_derate: float = 0.0,
    efficiency_loss: float = 0.0,
    water_constrained_cf: float | None = None,
) -> float:
    """Compose the channels into the stressed effective capacity factor.

    Each channel is a fraction in [0, 1]; they reduce the baseline CF multiplicatively. An
    optional ``water_constrained_cf`` hard-caps the result (drought cooling limit).
    """
    cf = _clamp01(cf_baseline)
    for channel in (dispatch_penalty, outage_rate, capacity_derate, efficiency_loss):
        cf *= 1.0 - _clamp01(channel)
    if water_constrained_cf is not None:
        cf = min(cf, _clamp01(water_constrained_cf))
    return _clamp01(cf)
