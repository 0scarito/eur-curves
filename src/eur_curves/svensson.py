"""Svensson (1994) yield-curve model, ECB parameterisation.

The ECB publishes six parameters daily for the euro-area AAA government
curve (Svensson model, continuous compounding, rates in percent per annum):

    y(t) = b0
         + b1 * (1 - exp(-t/tau1)) / (t/tau1)
         + b2 * [(1 - exp(-t/tau1)) / (t/tau1) - exp(-t/tau1)]
         + b3 * [(1 - exp(-t/tau2)) / (t/tau2) - exp(-t/tau2)]

All functions accept scalar or ``numpy`` array maturities ``t`` (in years)
and return the same shape. Rates are in percent, continuous compounding,
matching the ECB convention.
"""

from __future__ import annotations

import numpy as np

__all__ = ["spot_rate", "discount_factor", "forward_rate"]


def _g1(x: np.ndarray) -> np.ndarray:
    """(1 - exp(-x)) / x with the analytic limit 1 at x = 0."""
    with np.errstate(divide="ignore", invalid="ignore"):
        out = -np.expm1(-x) / x
    return np.where(x == 0.0, 1.0, out)


def _as_array(t) -> tuple[np.ndarray, bool]:
    arr = np.asarray(t, dtype=float)
    return arr, arr.ndim == 0


def spot_rate(t, b0: float, b1: float, b2: float, b3: float, tau1: float, tau2: float):
    """Continuously-compounded zero-coupon spot rate y(t), in percent.

    ``t`` is time to maturity in years (scalar or array, ``t >= 0``).
    At ``t = 0`` the analytic limit ``b0 + b1`` is returned.
    """
    arr, scalar = _as_array(t)
    x1 = arr / tau1
    x2 = arr / tau2
    g1 = _g1(x1)
    g2 = _g1(x2)
    y = b0 + b1 * g1 + b2 * (g1 - np.exp(-x1)) + b3 * (g2 - np.exp(-x2))
    return float(y) if scalar else y


def discount_factor(t, b0: float, b1: float, b2: float, b3: float, tau1: float, tau2: float):
    """Discount factor P(t) = exp(-y(t)/100 * t) (continuous compounding).

    The division by 100 converts the percent rate to a decimal.
    """
    arr, scalar = _as_array(t)
    y = spot_rate(arr, b0, b1, b2, b3, tau1, tau2)
    p = np.exp(-np.asarray(y) / 100.0 * arr)
    return float(p) if scalar else p


def forward_rate(t, b0: float, b1: float, b2: float, b3: float, tau1: float, tau2: float):
    """Instantaneous forward rate f(t), in percent.

    f(t) = d/dt [t * y(t)]
         = b0 + b1*exp(-t/tau1) + b2*(t/tau1)*exp(-t/tau1) + b3*(t/tau2)*exp(-t/tau2)

    At ``t = 0`` this equals ``b0 + b1``, the same short-end limit as the
    spot curve.
    """
    arr, scalar = _as_array(t)
    x1 = arr / tau1
    x2 = arr / tau2
    f = b0 + b1 * np.exp(-x1) + b2 * x1 * np.exp(-x1) + b3 * x2 * np.exp(-x2)
    return float(f) if scalar else f
