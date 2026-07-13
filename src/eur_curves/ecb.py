"""ECB Data Portal client for the euro-area AAA Svensson yield curve.

Data source: https://data-api.ecb.europa.eu (dataset ``YC``, series key
``B.U2.EUR.4F.G_N_A.SV_C_YM.<SERIES>``). No authentication required.

The portal serves CSV with (among others) the columns ``DATA_TYPE_FM``
(series short name, e.g. ``BETA0`` or ``SR_10Y``), ``TIME_PERIOD``
(ISO date) and ``OBS_VALUE`` (percent, continuous compounding).
"""

from __future__ import annotations

import datetime as dt
import io
from dataclasses import asdict, dataclass

import pandas as pd
import requests

__all__ = [
    "CurveParams",
    "PARAM_SERIES",
    "SPOT_TENORS",
    "fetch_params",
    "fetch_params_history",
    "fetch_published_spots",
    "fetch_spot_history",
    "parse_csv",
]

BASE_URL = "https://data-api.ecb.europa.eu/service/data/YC"
SERIES_PREFIX = "B.U2.EUR.4F.G_N_A.SV_C_YM"

PARAM_SERIES = ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")

#: Published zero-coupon spot-rate series and their maturities in years.
SPOT_TENORS: dict[str, float] = {
    "SR_3M": 0.25,
    "SR_6M": 0.5,
    "SR_1Y": 1.0,
    "SR_2Y": 2.0,
    "SR_5Y": 5.0,
    "SR_7Y": 7.0,
    "SR_10Y": 10.0,
    "SR_15Y": 15.0,
    "SR_20Y": 20.0,
    "SR_30Y": 30.0,
}

_TIMEOUT = 30


@dataclass(frozen=True)
class CurveParams:
    """One day's Svensson parameter set as published by the ECB."""

    date: dt.date
    beta0: float
    beta1: float
    beta2: float
    beta3: float
    tau1: float
    tau2: float

    def as_tuple(self) -> tuple[float, float, float, float, float, float]:
        """Positional (b0, b1, b2, b3, tau1, tau2) for the svensson module."""
        return (self.beta0, self.beta1, self.beta2, self.beta3, self.tau1, self.tau2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d


def parse_csv(text: str) -> pd.DataFrame:
    """Parse an ECB ``format=csvdata`` response.

    Returns a DataFrame with columns ``series`` (short name from
    ``DATA_TYPE_FM``), ``date`` (``datetime.date``) and ``value`` (float),
    sorted by (series, date).
    """
    frame = pd.read_csv(
        io.StringIO(text), usecols=["DATA_TYPE_FM", "TIME_PERIOD", "OBS_VALUE"]
    )
    frame = frame.rename(
        columns={"DATA_TYPE_FM": "series", "TIME_PERIOD": "date", "OBS_VALUE": "value"}
    )
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["value"] = frame["value"].astype(float)
    return frame.sort_values(["series", "date"]).reset_index(drop=True)


def _request(series: list[str] | tuple[str, ...], **params: str) -> pd.DataFrame:
    key = "+".join(series)
    url = f"{BASE_URL}/{SERIES_PREFIX}.{key}"
    query = {"format": "csvdata", **params}
    resp = requests.get(url, params=query, timeout=_TIMEOUT)
    resp.raise_for_status()
    if not resp.text.strip():
        raise ValueError(f"ECB returned an empty response for {key} ({params})")
    return parse_csv(resp.text)


def _frame_to_params(frame: pd.DataFrame, date: dt.date | None = None) -> CurveParams:
    """Build CurveParams from a parsed frame, using the latest common date."""
    pivot = frame.pivot(index="date", columns="series", values="value")
    missing = [s for s in PARAM_SERIES if s not in pivot.columns]
    if missing:
        raise ValueError(f"missing parameter series in response: {missing}")
    pivot = pivot.dropna(subset=list(PARAM_SERIES))
    if pivot.empty:
        raise ValueError("no date has all six Svensson parameters")
    row_date = date if date is not None else pivot.index.max()
    if row_date not in pivot.index:
        raise ValueError(f"no complete parameter set for {row_date}")
    row = pivot.loc[row_date]
    return CurveParams(
        date=row_date,
        beta0=float(row["BETA0"]),
        beta1=float(row["BETA1"]),
        beta2=float(row["BETA2"]),
        beta3=float(row["BETA3"]),
        tau1=float(row["TAU1"]),
        tau2=float(row["TAU2"]),
    )


def fetch_params(date: dt.date | str | None = None) -> CurveParams:
    """Fetch the six Svensson parameters for ``date`` (default: latest)."""
    if date is None:
        frame = _request(PARAM_SERIES, lastNObservations="1")
        return _frame_to_params(frame)
    date = dt.date.fromisoformat(date) if isinstance(date, str) else date
    iso = date.isoformat()
    frame = _request(PARAM_SERIES, startPeriod=iso, endPeriod=iso)
    return _frame_to_params(frame, date=date)


def fetch_params_history(start: dt.date | str, end: dt.date | str | None = None) -> pd.DataFrame:
    """Daily parameter history from ``start`` (wide frame indexed by date)."""
    params = {"startPeriod": str(start)}
    if end is not None:
        params["endPeriod"] = str(end)
    frame = _request(PARAM_SERIES, **params)
    return frame.pivot(index="date", columns="series", values="value")


def fetch_published_spots(date: dt.date | str | None = None) -> tuple[dt.date, dict[str, float]]:
    """Fetch the ECB-published zero-coupon spot rates (percent).

    Returns ``(date, {series: rate})`` for the requested date, or for the
    latest date common to all published tenors when ``date`` is None.
    """
    series = tuple(SPOT_TENORS)
    if date is None:
        frame = _request(series, lastNObservations="1")
    else:
        date = dt.date.fromisoformat(date) if isinstance(date, str) else date
        iso = date.isoformat()
        frame = _request(series, startPeriod=iso, endPeriod=iso)
    pivot = frame.pivot(index="date", columns="series", values="value").dropna()
    if pivot.empty:
        raise ValueError("no date has all published spot tenors")
    row_date = pivot.index.max()
    return row_date, {s: float(pivot.loc[row_date, s]) for s in series}


def fetch_spot_history(
    series: list[str] | tuple[str, ...],
    start: dt.date | str,
    end: dt.date | str | None = None,
) -> pd.DataFrame:
    """History of published spot-rate series (wide frame indexed by date)."""
    unknown = [s for s in series if s not in SPOT_TENORS]
    if unknown:
        raise ValueError(f"unknown spot series: {unknown}")
    params = {"startPeriod": str(start)}
    if end is not None:
        params["endPeriod"] = str(end)
    frame = _request(tuple(series), **params)
    return frame.pivot(index="date", columns="series", values="value")
