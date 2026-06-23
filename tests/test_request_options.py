"""The physical-run request must carry run-config options through to the worker.

Options (e.g. the opt-in Knutson TC future method) are set in the UI on
``RunConfig.options`` and forwarded verbatim so the worker can branch on them.
"""

from __future__ import annotations

from climaterisk.core.entities import Portfolio, RunConfig, Scenario
from climaterisk.engines.base import PhysicalRunRequest


def test_options_forwarded_to_request() -> None:
    portfolio = Portfolio(
        run_config=RunConfig(options={"tc_future_method": "knutson"}),
        scenario=Scenario(),
    )
    req = PhysicalRunRequest.from_portfolio(portfolio)
    assert req.options == {"tc_future_method": "knutson"}


def test_options_default_empty() -> None:
    req = PhysicalRunRequest.from_portfolio(Portfolio())
    assert req.options == {}
