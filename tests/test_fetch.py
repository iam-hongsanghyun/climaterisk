"""Open-data fetcher — URL resolution / templating / safety (offline, hermetic)."""

from __future__ import annotations

import pytest

from climaterisk.data.fetch import resolve_url


def test_resolve_plain_url() -> None:
    assert resolve_url({"id": "x", "download_url": "https://h/f.tif"}, None) == "https://h/f.tif"


def test_resolve_templated_by_country() -> None:
    src = {"id": "x", "download_url": "https://h/{iso3}/{iso3_lower}.tif"}
    assert resolve_url(src, "jpn") == "https://h/JPN/jpn.tif"


def test_resolve_templated_needs_country() -> None:
    src = {"id": "x", "download_url": "https://h/{iso3}.tif"}
    with pytest.raises(ValueError, match="per-country"):
        resolve_url(src, None)


def test_resolve_no_url_is_actionable() -> None:
    with pytest.raises(ValueError, match="no direct download URL"):
        resolve_url({"id": "x", "url": "https://portal"}, None)


def test_resolve_rejects_non_https() -> None:
    with pytest.raises(ValueError, match="https"):
        resolve_url({"id": "x", "download_url": "http://h/f.tif"}, None)
