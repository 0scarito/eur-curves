"""Offline tests for the fixed-income analytics layer.

All tests use a fixed Svensson parameter set (the ECB euro-area AAA curve
published for 2026-07-10, the same one pinned in ``test_svensson.py``), so they
are network-free and fully reproducible.
"""

import datetime as dt

import numpy as np
import pytest

from eur_curves.bonds import (
    Bond,
    convexity,
    dv01,
    macaulay_duration,
    modified_duration,
    par_coupon,
    parallel_shift,
    price,
    yield_to_maturity,
)
from eur_curves.ecb import CurveParams
from eur_curves.svensson import spot_rate

# ECB euro-area AAA Svensson parameters, 2026-07-10 (percent, cont. comp.)
PARAMS = CurveParams(
    date=dt.date(2026, 7, 10),
    beta0=1.3035816676,
    beta1=0.8859235246,
    beta2=1.6170537131,
    beta3=7.4347832397,
    tau1=1.0113851993,
    tau2=15.9471664368,
)

FACE = 100.0


# --------------------------------------------------------------------------- #
# cashflow schedule
# --------------------------------------------------------------------------- #
def test_annual_bond_cashflows():
    times, amounts = Bond(FACE, 0.05, 3).cashflows()
    assert times.tolist() == [1.0, 2.0, 3.0]
    assert amounts.tolist() == [5.0, 5.0, 105.0]


def test_semiannual_bond_cashflows():
    times, amounts = Bond(FACE, 0.04, 2, coupons_per_year=2).cashflows()
    assert times.tolist() == [0.5, 1.0, 1.5, 2.0]
    assert amounts.tolist() == [2.0, 2.0, 2.0, 102.0]


def test_zero_coupon_has_single_cashflow():
    times, amounts = Bond(FACE, 0.0, 7).cashflows()
    assert times.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    assert amounts.tolist() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, FACE]


def test_fractional_periods_rejected():
    with pytest.raises(ValueError, match="whole number of periods"):
        Bond(FACE, 0.03, 2.5, coupons_per_year=1).cashflows()


def test_no_cashflows_rejected():
    with pytest.raises(ValueError, match="no cashflows"):
        Bond(FACE, 0.03, 0.4, coupons_per_year=1).cashflows()


# --------------------------------------------------------------------------- #
# par bond: coupon -> par -> YTM
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("maturity", [2.0, 5.0, 10.0, 30.0])
def test_par_coupon_prices_to_face(maturity):
    coupon = par_coupon(PARAMS, maturity)
    bond = Bond(FACE, coupon, maturity)
    assert price(bond, PARAMS) == pytest.approx(FACE, rel=1e-12)


@pytest.mark.parametrize("maturity", [2.0, 5.0, 10.0, 30.0])
def test_par_bond_ytm_equals_coupon(maturity):
    """For an annual bond priced at par, the effective-annual YTM == coupon."""
    coupon = par_coupon(PARAMS, maturity)
    bond = Bond(FACE, coupon, maturity)
    y = yield_to_maturity(bond, price(bond, PARAMS))
    assert y == pytest.approx(coupon, rel=1e-9)


def test_par_coupon_semiannual_prices_to_face():
    coupon = par_coupon(PARAMS, 10.0, coupons_per_year=2)
    bond = Bond(FACE, coupon, 10.0, coupons_per_year=2)
    assert price(bond, PARAMS) == pytest.approx(FACE, rel=1e-12)


def test_ytm_round_trips_price():
    bond = Bond(FACE, 0.035, 12)
    p = price(bond, PARAMS)
    y = yield_to_maturity(bond, p)
    times, amounts = bond.cashflows()
    reconstructed = float(np.sum(amounts * (1.0 + y) ** (-times)))
    assert reconstructed == pytest.approx(p, rel=1e-12)


# --------------------------------------------------------------------------- #
# DV01 vs an independent bump-and-reprice
# --------------------------------------------------------------------------- #
def _manual_price(bond: Bond, params: CurveParams, shift_bp: float) -> float:
    """Reprice by adding shift_bp*0.01% straight onto the spot outputs.

    Independent of ``dv01``'s beta0-bump code path; both are exact parallel
    shifts so they must agree to machine precision.
    """
    times, amounts = bond.cashflows()
    y = spot_rate(times, *params.as_tuple()) + shift_bp * 0.01  # percent, shifted
    dfs = np.exp(-y / 100.0 * times)
    return float(np.sum(amounts * dfs))


@pytest.mark.parametrize("maturity", [2.0, 10.0, 30.0])
def test_dv01_matches_finite_difference(maturity):
    coupon = par_coupon(PARAMS, maturity)
    bond = Bond(FACE, coupon, maturity)
    manual = (_manual_price(bond, PARAMS, -1.0) - _manual_price(bond, PARAMS, 1.0)) / 2.0
    assert dv01(bond, PARAMS) == pytest.approx(manual, rel=1e-9)
    assert dv01(bond, PARAMS) > 0.0


def test_dv01_rises_with_maturity():
    """Longer par bonds carry more rate risk per unit face."""
    dvs = [dv01(Bond(FACE, par_coupon(PARAMS, m), m), PARAMS) for m in (2.0, 5.0, 10.0, 30.0)]
    assert dvs == sorted(dvs)


# --------------------------------------------------------------------------- #
# duration & convexity
# --------------------------------------------------------------------------- #
def test_modified_equals_macaulay_over_one_plus_y():
    bond = Bond(FACE, 0.04, 10)
    mac = macaulay_duration(bond, PARAMS)
    y = yield_to_maturity(bond, price(bond, PARAMS))
    assert modified_duration(bond, PARAMS) == pytest.approx(mac / (1.0 + y), rel=1e-12)


@pytest.mark.parametrize("maturity", [1.0, 5.0, 10.0, 20.0])
def test_zero_coupon_macaulay_equals_maturity(maturity):
    bond = Bond(FACE, 0.0, maturity)
    assert macaulay_duration(bond, PARAMS) == pytest.approx(maturity, rel=1e-12)


def test_macaulay_below_maturity_for_coupon_bond():
    bond = Bond(FACE, 0.05, 10)
    assert macaulay_duration(bond, PARAMS) < 10.0


def test_convexity_is_positive():
    for bond in (Bond(FACE, 0.0, 10), Bond(FACE, 0.05, 10), Bond(FACE, 0.03, 30)):
        assert convexity(bond, PARAMS) > 0.0


def test_convexity_exceeds_duration_for_long_bonds():
    """sum(t^2 PV) / sum(PV) >= (sum(t PV)/sum(PV))^2 by Jensen; strict here."""
    bond = Bond(FACE, 0.03, 30)
    assert convexity(bond, PARAMS) > macaulay_duration(bond, PARAMS) ** 2


# --------------------------------------------------------------------------- #
# monotonicity in yield
# --------------------------------------------------------------------------- #
def test_price_decreases_as_yield_rises():
    bond = Bond(FACE, 0.04, 15)
    prices = [price(bond, parallel_shift(PARAMS, bp)) for bp in (-100.0, -25.0, 0.0, 25.0, 100.0)]
    assert prices == sorted(prices, reverse=True)


def test_parallel_shift_lifts_every_spot_by_the_bump():
    shifted = parallel_shift(PARAMS, 5.0)  # +5 bp
    t = np.array([0.5, 2.0, 10.0, 30.0])
    base = spot_rate(t, *PARAMS.as_tuple())
    bumped = spot_rate(t, *shifted.as_tuple())
    assert np.allclose(bumped - base, 0.05)  # 5 bp == 0.05 percent, at every tenor
