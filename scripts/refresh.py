"""Daily refresh: fetch the latest ECB curve, validate, snapshot, chart.

Steps
-----
1. Fetch the latest Svensson parameters and the ECB-published zero-coupon
   spot rates for the same reference date.
2. Validate: evaluate our ``spot_rate`` at each published tenor and compare
   with the ECB's own numbers. The max absolute error must be <= 0.5 bp,
   otherwise the script exits non-zero (the model or the data changed).
3. Write ``data/latest.json`` and render ``charts/curve.png`` +
   ``charts/history.png`` (2Y & 10Y, ~2 years of history).

Run from the repo root: ``python scripts/refresh.py``
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from eur_curves import ecb, plots, svensson

REPO_ROOT = Path(__file__).resolve().parents[1]
TOLERANCE_BP = 0.5
HISTORY_DAYS = 730


def main() -> int:
    params = ecb.fetch_params()
    spot_date, published = ecb.fetch_published_spots(date=params.date)
    if spot_date != params.date:
        print(f"date mismatch: params {params.date} vs spots {spot_date}", file=sys.stderr)
        return 1

    print(f"Reference date: {params.date}")
    print(f"Parameters: {params.to_dict()}")

    # --- validate our Svensson evaluation against the ECB's published spots
    rows = []
    for series, tenor in ecb.SPOT_TENORS.items():
        ours = svensson.spot_rate(tenor, *params.as_tuple())
        theirs = published[series]
        err_bp = (ours - theirs) * 100.0  # percent -> basis points
        rows.append((series, tenor, theirs, ours, err_bp))

    cols = ("series", "tenor", "ECB published", "our spot_rate", "err (bp)")
    print(f"\n{cols[0]:>7} {cols[1]:>6} {cols[2]:>14} {cols[3]:>14} {cols[4]:>10}")
    for series, tenor, theirs, ours, err_bp in rows:
        print(f"{series:>7} {tenor:>6.2f} {theirs:>14.6f} {ours:>14.6f} {err_bp:>10.6f}")

    max_err_bp = max(abs(r[4]) for r in rows)
    print(f"\nmax |error|: {max_err_bp:.6f} bp (tolerance {TOLERANCE_BP} bp)")
    if max_err_bp > TOLERANCE_BP:
        print("VALIDATION FAILED — not writing snapshot", file=sys.stderr)
        return 1
    print("validation OK")

    # --- snapshot
    snapshot = {
        "date": params.date.isoformat(),
        "source": "ECB Data Portal, dataset YC, series B.U2.EUR.4F.G_N_A.SV_C_YM.*",
        "convention": "percent, continuous compounding, ACT/365-style year fractions",
        "params": params.to_dict(),
        "published_spots": {s: published[s] for s in ecb.SPOT_TENORS},
        "fitted_spots": {s: r[3] for s, r in zip(ecb.SPOT_TENORS, rows)},
        "max_abs_error_bp": max_err_bp,
        "refreshed_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    data_path = REPO_ROOT / "data" / "latest.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {data_path.relative_to(REPO_ROOT)}")

    # --- charts
    curve_png = plots.plot_curve(params, REPO_ROOT / "charts" / "curve.png")
    print(f"wrote {curve_png.relative_to(REPO_ROOT)}")

    # par-bond ladder DV01 / duration — needs only the fitted params (no network)
    bonds_png = plots.plot_bond_ladder(params, REPO_ROOT / "charts" / "bonds.png")
    print(f"wrote {bonds_png.relative_to(REPO_ROOT)}")

    start = params.date - dt.timedelta(days=HISTORY_DAYS)
    history = ecb.fetch_spot_history(["SR_2Y", "SR_10Y"], start=start)
    hist_png = plots.plot_history(history, REPO_ROOT / "charts" / "history.png")
    print(f"wrote {hist_png.relative_to(REPO_ROOT)} ({len(history)} business days)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
