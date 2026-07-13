"""Charts for the daily refresh: today's curve and the 2Y/10Y history."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .ecb import CurveParams  # noqa: E402
from .svensson import forward_rate, spot_rate  # noqa: E402

__all__ = ["plot_curve", "plot_history"]

_SPOT_COLOR = "#1f6feb"
_FWD_COLOR = "#d29922"


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
