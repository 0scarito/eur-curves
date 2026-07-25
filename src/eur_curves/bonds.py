"""Fixed-income analytics on top of a fitted Svensson discount curve.

Everything here prices bullet fixed-coupon bonds off a single day's ECB
:class:`~eur_curves.ecb.CurveParams` — that is, off the euro-area AAA
government zero-coupon curve — using :func:`eur_curves.svensson.discount_factor`
as the discount function. Nothing is fitted here; the curve is taken as given.

Conventions
-----------
* Bond cashflows fall on ``t = i / coupons_per_year`` years, ``i = 1..N``,
  with a level coupon ``face * annual_coupon_rate / coupons_per_year`` each
  period and the face repaid at maturity. ``annual_coupon_rate`` is a decimal
  fraction (``0.03`` == 3%).
* Curve discounting is **continuous compounding in percent** — the native ECB
  convention of the :mod:`~eur_curves.svensson` module. ``price`` therefore
  discounts each cashflow by ``exp(-y(t)/100 * t)``.
* Yield to maturity is quoted as an **effective annual rate** ``y`` (decimal):
  a single constant rate for which ``sum(cf * (1 + y) ** -t) == price``. This
  discrete convention is what makes ``modified = macaulay / (1 + y)`` exact
  (see :func:`modified_duration`) and a par bond's YTM equal to its coupon.
* A parallel shift of the curve is exact for Svensson: ``beta0`` enters
  ``y(t)`` additively, so lifting ``beta0`` by ``shift_bp * 0.01`` percent adds
  exactly ``shift_bp`` basis points to the spot rate at **every** maturity
  (see :func:`parallel_shift`). One basis point is ``0.01`` in the percent
  scale the curve uses.

Reference: Fabozzi, F.J. (ed.), *The Handbook of Fixed Income Securities*,
for the standard duration/convexity/DV01 definitions used below.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import brentq

from .ecb import CurveParams
from .svensson import discount_factor

__all__ = [
    "Bond",
    "parallel_shift",
    "price",
    "par_coupon",
    "yield_to_maturity",
    "dv01",
    "macaulay_duration",
    "modified_duration",
    "convexity",
]


@dataclass(frozen=True)
class Bond:
    """A bullet fixed-coupon bond.

    Parameters
    ----------
    face:
        Redemption amount, repaid in full at maturity (e.g. ``100.0``).
    annual_coupon_rate:
        Annual coupon as a decimal fraction of face (``0.03`` == 3% p.a.).
    maturity_years:
        Time to maturity in years; ``maturity_years * coupons_per_year`` must
        be a whole number of periods.
    coupons_per_year:
        Coupon frequency (``1`` = annual, ``2`` = semi-annual, ...).
    """

    face: float
    annual_coupon_rate: float
    maturity_years: float
    coupons_per_year: int = 1

    def cashflows(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(times, amounts)`` for the bond.

        ``times`` are the coupon dates ``i / coupons_per_year`` in years for
        ``i = 1..N``; ``amounts`` is the level coupon each period with the face
        added onto the final one.
        """
        m = int(self.coupons_per_year)
        n_float = self.maturity_years * m
        n = int(round(n_float))
        if n < 1:
            raise ValueError("bond has no cashflows (maturity_years * coupons_per_year < 1)")
        if abs(n_float - n) > 1e-9:
            raise ValueError(
                "maturity_years * coupons_per_year must be a whole number of periods"
            )
        times = np.arange(1, n + 1, dtype=float) / m
        coupon = self.face * self.annual_coupon_rate / m
        amounts = np.full(n, coupon, dtype=float)
        amounts[-1] += self.face
        return times, amounts


def parallel_shift(params: CurveParams, shift_bp: float) -> CurveParams:
    """Return ``params`` with the whole spot curve shifted by ``shift_bp`` bp.

    Because ``beta0`` enters the Svensson spot rate additively, adding
    ``shift_bp * 0.01`` percent to ``beta0`` raises ``y(t)`` by exactly
    ``shift_bp`` basis points at every maturity — an exact parallel shift, with
    no re-fitting and no per-tenor bumping. (``0.01`` percent == 1 bp.)
    """
    return replace(params, beta0=params.beta0 + shift_bp * 0.01)


def price(bond: Bond, params: CurveParams) -> float:
    """Dirty price: present value of every cashflow off the curve.

    ``price = sum(cf * discount_factor(t, params))`` with continuous-compounding
    discount factors. Valued as of today (``t = 0``); with no accrued interest
    the dirty price equals the clean price.
    """
    times, amounts = bond.cashflows()
    dfs = discount_factor(times, *params.as_tuple())
    return float(np.sum(amounts * dfs))


def par_coupon(params: CurveParams, maturity_years: float, coupons_per_year: int = 1) -> float:
    """Annual coupon rate (decimal) that prices a bullet bond to par off the curve.

    Closed form: ``c = (1 - P(T)) / annuity`` where ``annuity`` is the sum of
    discount factors over the coupon dates divided by the frequency — the usual
    par-yield formula. Handy for building a par ladder.
    """
    m = int(coupons_per_year)
    n = int(round(maturity_years * m))
    if n < 1:
        raise ValueError("maturity too short for one coupon period")
    times = np.arange(1, n + 1, dtype=float) / m
    dfs = np.asarray(discount_factor(times, *params.as_tuple()), dtype=float)
    annuity = dfs.sum() / m
    return float((1.0 - dfs[-1]) / annuity)


def yield_to_maturity(bond: Bond, price: float) -> float:
    """Solve for the effective annual yield ``y`` s.t. ``sum(cf*(1+y)**-t) == price``.

    Root-found with Brent's method on ``(-0.99, 10.0)``. ``y`` is a decimal
    effective annual rate (discrete compounding, ``(1 + y) ** -t``), the
    convention that makes a par bond's YTM equal its coupon exactly.
    """
    times, amounts = bond.cashflows()

    def residual(y: float) -> float:
        return float(np.sum(amounts * (1.0 + y) ** (-times)) - price)

    return float(brentq(residual, -0.99, 10.0, xtol=1e-14, rtol=1e-14))


def dv01(bond: Bond, params: CurveParams) -> float:
    """Price change for a 1 bp parallel move of the curve (positive number).

    Central difference of a +/-1 bp parallel shift:
    ``(P(-1bp) - P(+1bp)) / 2``. Lower yields raise the price, so the result is
    positive; it is the price gain per 1 bp fall in rates (in the same units as
    ``face``).
    """
    up = price(bond, parallel_shift(params, +1.0))
    down = price(bond, parallel_shift(params, -1.0))
    return (down - up) / 2.0


def _present_values(bond: Bond, params: CurveParams) -> tuple[np.ndarray, np.ndarray]:
    """``(times, pv)`` where ``pv`` are curve-discounted cashflow present values."""
    times, amounts = bond.cashflows()
    pv = amounts * np.asarray(discount_factor(times, *params.as_tuple()), dtype=float)
    return times, pv


def macaulay_duration(bond: Bond, params: CurveParams) -> float:
    """PV-weighted average time to cashflow: ``sum(t * PV_cf) / price``.

    A zero-coupon bond has Macaulay duration equal to its maturity.
    """
    times, pv = _present_values(bond, params)
    return float(np.sum(times * pv) / pv.sum())


def modified_duration(bond: Bond, params: CurveParams) -> float:
    """Macaulay duration divided by ``(1 + y)``, using the bond's YTM ``y``.

    With the effective-annual discounting ``P(y) = sum cf*(1+y)**-t`` we have
    ``dP/dy = -sum t*cf*(1+y)**(-t-1) = -macaulay/(1+y) * P``, so this is the
    exact ``-1/P * dP/dy`` sensitivity for a 100% (1.0) change in ``y``.
    """
    mac = macaulay_duration(bond, params)
    y = yield_to_maturity(bond, price(bond, params))
    return mac / (1.0 + y)


def convexity(bond: Bond, params: CurveParams) -> float:
    """PV-weighted average squared time: ``sum(t**2 * PV_cf) / price``.

    The continuous-compounding analogue of convexity; strictly positive for any
    bond with positive cashflows.
    """
    times, pv = _present_values(bond, params)
    return float(np.sum(times**2 * pv) / pv.sum())
