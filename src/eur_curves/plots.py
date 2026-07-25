"""Charts for the daily refresh: today's curve and the 2Y/10Y history."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .bonds import Bond, dv01, modified_duration, par_coupon  # noqa: E402
from .ecb import CurveParams  # noqa: E402
from .svensson import forward_rate, spot_rate  # noqa: E402

__all__ = ["plot_curve", "plot_history", "plot_bond_ladder"]

_SPOT_COLOR = "#1f6feb"
_FWD_COLOR = "#d29922"

#: Maturities (years) of the par-bond ladder in :func:`plot_bond_ladder`.
_LADDER_TENORS = (1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0)


def plot_curve(params: CurveParams, path: str | Path) -> Path:
    """Spot + instantaneous forward curve, 0.25y to 30y, saved as PNG."""
    t = np.linspace(0.25, 30.0, 400)
    spot = spot_rate(t, *params.as_tuple())
    fwd = forward_rate(t, *params.as_tuple())

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    ax.plot(t, spot, color=_SPOT_COLOR, lw=2, label="Zero-coupon spot")
    ax.plot(t, fwd, color=_FWD_COLOR, lw=2, ls="--", label="Instantaneous forward")
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel("Rate (%, continuous compounding)")
    ax.set_title(f"Euro-area AAA government curve — {params.date.isoformat()} (ECB, Svensson)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 30)
    fig.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_bond_ladder(params: CurveParams, path: str | Path, face: float = 100.0) -> Path:
    """Risk of a ladder of par bonds priced off today's curve, saved as PNG.

    For each maturity in :data:`_LADDER_TENORS` a bullet bond is struck at its
    par coupon off ``params`` (so it prices to ``face``) and its DV01 and
    modified duration are plotted against maturity — DV01 as bars (left axis),
    modified duration as a line (right axis).
    """
    tenors = np.array(_LADDER_TENORS)
    dv01s = np.empty_like(tenors)
    mod_durs = np.empty_like(tenors)
    for i, mat in enumerate(_LADDER_TENORS):
        coupon = par_coupon(params, mat)
        bond = Bond(face=face, annual_coupon_rate=coupon, maturity_years=mat)
        dv01s[i] = dv01(bond, params)
        mod_durs[i] = modified_duration(bond, params)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    ax.bar(tenors, dv01s, width=0.7, color=_SPOT_COLOR, alpha=0.85, label="DV01")
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel(f"DV01 (price change per 1 bp, per {face:g} face)")
    ax.set_title(
        f"Par-bond ladder risk — {params.date.isoformat()} (ECB euro-area AAA curve)"
    )
    ax.set_xticks(tenors)
    ax.set_xticklabels([f"{t:g}" for t in tenors])
    ax.grid(axis="y", alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(tenors, mod_durs, color=_FWD_COLOR, lw=2, marker="o", label="Modified duration")
    ax2.set_ylabel("Modified duration (years)")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False, loc="upper left")
    fig.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_history(history: pd.DataFrame, path: str | Path) -> Path:
    """History of published spot series (e.g. SR_2Y, SR_10Y), saved as PNG.

    ``history`` is a wide frame indexed by date with one column per series,
    as returned by :func:`eur_curves.ecb.fetch_spot_history`.
    """
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    labels = {"SR_2Y": "2Y", "SR_10Y": "10Y"}
    colors = {"SR_2Y": _SPOT_COLOR, "SR_10Y": _FWD_COLOR}
    for col in history.columns:
        ax.plot(
            history.index,
            history[col],
            lw=1.5,
            label=labels.get(col, col),
            color=colors.get(col),
        )
    ax.set_xlabel("Date")
    ax.set_ylabel("Rate (%, continuous compounding)")
    ax.set_title("Euro-area AAA zero-coupon yields (ECB)")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
