"""Tests for the ECB Data Portal parsing (offline, real captured responses)."""

import datetime as dt
import os
from pathlib import Path

import pytest

from eur_curves import ecb

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_csv_params_fixture():
    """Fixture is a verbatim ECB csvdata response (6 param series, 1 day)."""
    frame = ecb.parse_csv(_read("params_latest.csv"))
    assert list(frame.columns) == ["series", "date", "value"]
    assert len(frame) == 6
    assert set(frame["series"]) == set(ecb.PARAM_SERIES)
    assert set(frame["date"]) == {dt.date(2026, 7, 10)}
    row = frame.set_index("series")["value"]
    assert row["BETA0"] == pytest.approx(1.3035816676, rel=1e-12)
    assert row["TAU2"] == pytest.approx(15.9471664368, rel=1e-12)


def test_frame_to_params_from_fixture():
    frame = ecb.parse_csv(_read("params_latest.csv"))
    params = ecb._frame_to_params(frame)
    assert params.date == dt.date(2026, 7, 10)
    assert params.as_tuple() == pytest.approx(
        (1.3035816676, 0.8859235246, 1.6170537131, 7.4347832397, 1.0113851993, 15.9471664368),
        rel=1e-12,
    )
    d = params.to_dict()
    assert d["date"] == "2026-07-10"
    assert d["beta0"] == pytest.approx(1.3035816676)


def test_frame_to_params_picks_latest_complete_date():
    """When a date lacks a parameter, the latest complete date wins."""
    frame = ecb.parse_csv(_read("params_latest.csv"))
    # drop TAU2 to make the only date incomplete -> must raise
    broken = frame[frame["series"] != "TAU2"].reset_index(drop=True)
    with pytest.raises(ValueError):
        ecb._frame_to_params(broken)


def test_parse_csv_spots_fixture():
    """Fixture holds SR_1Y and SR_10Y over two business days."""
    frame = ecb.parse_csv(_read("spots_two_days.csv"))
    assert len(frame) == 4
    assert set(frame["series"]) == {"SR_1Y", "SR_10Y"}
    pivot = frame.pivot(index="date", columns="series", values="value")
    assert pivot.loc[dt.date(2026, 7, 10), "SR_10Y"] == pytest.approx(3.1085540184, rel=1e-12)
    assert pivot.loc[dt.date(2026, 7, 9), "SR_1Y"] == pytest.approx(2.5257754748, rel=1e-12)


def test_spot_tenor_map_is_complete():
    assert len(ecb.SPOT_TENORS) == 10
    assert ecb.SPOT_TENORS["SR_3M"] == 0.25
    assert ecb.SPOT_TENORS["SR_30Y"] == 30.0


def test_fetch_spot_history_rejects_unknown_series():
    with pytest.raises(ValueError, match="unknown spot series"):
        ecb.fetch_spot_history(["SR_9Y"], start="2026-01-01")


@pytest.mark.network
@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="live ECB API test; set RUN_NETWORK_TESTS=1 to enable",
)
def test_live_params_reproduce_published_spots():
    """End-to-end: latest params must reproduce published spots to 0.5 bp."""
    from eur_curves.svensson import spot_rate

    params = ecb.fetch_params()
    spot_date, published = ecb.fetch_published_spots(date=params.date)
    assert spot_date == params.date
    for series, tenor in ecb.SPOT_TENORS.items():
        ours = spot_rate(tenor, *params.as_tuple())
        assert abs(ours - published[series]) * 100.0 <= 0.5  # basis points
