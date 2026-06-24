"""Glue between a completed run and the finance core: resolve profiles (override →
portfolio → cited defaults), turn per-asset AAI + transition cost into the annual climate
loss, and run :func:`core.assess` at the portfolio level and per overridden asset."""

from __future__ import annotations

from typing import Any

from climaterisk.core.entities import FinancialProfile, Portfolio
from climaterisk.finance import core


def _defaults(ref: dict[str, Any]) -> dict[str, float]:
    return {k: float(v["value"]) for k, v in ref["financing_defaults"].items()}


def resolve_profile(
    primary: FinancialProfile | None,
    fallback: FinancialProfile | None,
    ref: dict[str, Any],
) -> core.FinancialProfile:
    """Field-by-field: per-asset override → portfolio default → cited financing defaults."""
    d = _defaults(ref)

    def pick(attr: str, default: float) -> float:
        for src in (primary, fallback):
            v = getattr(src, attr, None) if src else None
            if v is not None:
                return float(v)
        return float(default)

    return core.FinancialProfile(
        capex=pick("capex", 0.0),
        annual_ebitda=pick("annual_ebitda", 0.0),
        horizon_years=int(pick("horizon_years", d["horizon_years"])),
        debt_fraction=pick("debt_fraction", d["debt_fraction"]),
        debt_tenor_years=int(pick("debt_tenor_years", d["debt_tenor_years"])),
        risk_free_rate=pick("risk_free_rate", d["risk_free_rate"]),
        baseline_spread_bps=pick("baseline_spread_bps", d["baseline_spread_bps"]),
        baseline_equity_rate=pick("baseline_equity_rate", d["baseline_equity_rate"]),
    )


def resolve_rating_method(profile: FinancialProfile | None, ref: dict[str, Any]) -> dict[str, Any]:
    """Resolve which DSCR→rating grid to use: a per-portfolio 'custom' grid, a named method
    from ``rating_methods``, or the library default. Returns the thresholds plus display
    metadata (id/label/source) so the result can show the methodology that was applied."""
    methods: dict[str, Any] = ref.get("rating_methods", {})
    default_id = str(ref.get("default_rating_method", "moodys_sp"))
    chosen = (profile.rating_method if profile else None) or default_id

    if chosen == "custom" and profile and profile.custom_rating_thresholds:
        thresholds = [t.model_dump() for t in profile.custom_rating_thresholds]
        return {
            "method": "custom",
            "label": "Custom (user-defined)",
            "source": "User-defined DSCR→rating grid",
            "thresholds": thresholds,
        }

    method = methods.get(chosen) or methods.get(default_id)
    if method is not None:
        return {
            "method": chosen if chosen in methods else default_id,
            "label": method.get("label", chosen),
            "source": method.get("source", ""),
            "thresholds": method["thresholds"],
        }
    # Last-resort fallback for older libraries without rating_methods.
    return {
        "method": "moodys_sp",
        "label": "Moody's / S&P",
        "source": "",
        "thresholds": ref["rating_dscr_thresholds"],
    }


def per_asset_aai(run_output: dict[str, Any]) -> dict[str, float]:
    """Sum each asset's expected annual impact across all OK perils in a physical run."""
    loss: dict[str, float] = {}
    for r in run_output.get("results", []):
        if r.get("status") != "ok":
            continue
        for pa in r.get("per_asset", []):
            loss[pa["id"]] = loss.get(pa["id"], 0.0) + float(pa.get("eai", 0.0) or 0.0)
    return loss


def compute_finance(
    portfolio: Portfolio,
    run_output: dict[str, Any],
    transition_annual_cost: float,
    ref: dict[str, Any],
) -> dict[str, Any]:
    """Portfolio-level + per-asset-override climate-risk-premium assessment for a run."""
    aai = per_asset_aai(run_output)
    total_physical = sum(aai.values())
    port_ep = portfolio.run_config.financial_profile
    port_loss = total_physical + max(0.0, transition_annual_cost)

    # The DSCR→rating methodology is a portfolio-level "house view": resolve it once and
    # apply the same grid to the portfolio and every per-asset assessment by swapping it
    # into an effective ref (core reads ref["rating_dscr_thresholds"]).
    rating = resolve_rating_method(port_ep, ref)
    eff_ref = {**ref, "rating_dscr_thresholds": rating["thresholds"]}

    portfolio_result = core.assess(resolve_profile(port_ep, None, ref), port_loss, eff_ref)

    per_asset: list[dict[str, Any]] = []
    for a in portfolio.assets:
        if a.financial_profile is None:
            continue  # only assets with their own profile get a per-asset CRP
        res = core.assess(
            resolve_profile(a.financial_profile, port_ep, ref), aai.get(a.id, 0.0), eff_ref
        )
        per_asset.append(
            {"id": a.id, "name": a.name, "annual_climate_loss": aai.get(a.id, 0.0), **res}
        )

    cur = portfolio.assets[0].currency if portfolio.assets else "USD"
    return {
        "currency": cur,
        "total_physical_aai": total_physical,
        "transition_annual_cost": max(0.0, transition_annual_cost),
        "rating_method": rating["method"],
        "rating_method_label": rating["label"],
        "rating_method_source": rating["source"],
        "rating_thresholds": rating["thresholds"],
        "portfolio": portfolio_result,
        "per_asset": per_asset,
        "detail": (
            f"Climate risk premium {portfolio_result['crp_bps']:+.0f} bps "
            f"({portfolio_result['baseline']['rating']} → {portfolio_result['stressed']['rating']})"
        ),
    }
