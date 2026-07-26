"""Key-rate duration tests — Ho (1992), all offline (fixed Svensson params)."""

import datetime as dt

import numpy as np
import pytest

from eur_curves.bonds import Bond, dv01
from eur_curves.ecb import CurveParams
from eur_curves.keyrate import (
    DEFAULT_KEY_TENORS,
    key_rate_durations,
    key_rate_dv01,
    parallel_dv01_from_keys,
    tent_weight,
)

# A realistic, upward-sloping euro-area AAA-ish curve (percent).
PARAMS = CurveParams(
    date=dt.date(2026, 7, 26),
    beta0=2.5, beta1=-1.5, beta2=-1.0, beta3=1.0, tau1=1.5, tau2=10.0,
)


def test_tent_weights_partition_unity():
    """The tents sum to 1 at every maturity — the property that makes the
    key-rate DV01s add up to the parallel DV01."""
    keys = np.asarray(DEFAULT_KEY_TENORS)
    t = np.linspace(0.0, 40.0, 400)
    total = sum(tent_weight(t, keys, i) for i in range(len(keys)))
    np.testing.assert_allclose(total, 1.0, atol=1e-12)


def test_tent_is_one_at_its_key_zero_at_neighbours():
    keys = np.asarray(DEFAULT_KEY_TENORS)  # (2, 5, 10, 30)
    w = tent_weight(keys, keys, 1)  # the 5y tent, evaluated at every key
    np.testing.assert_allclose(w, [0.0, 1.0, 0.0, 0.0], atol=1e-12)


def test_key_rate_dv01s_sum_to_parallel_dv01():
    """The headline identity: sum of KR01s == parallel DV01."""
    bond = Bond(face=100.0, annual_coupon_rate=0.03, maturity_years=10.0)
    total, parallel = parallel_dv01_from_keys(bond, PARAMS)
    assert parallel == pytest.approx(total, rel=1e-6)


def test_risk_concentrates_at_the_maturity_bucket():
    """A 10-year zero's rate risk sits almost entirely in the 10y key, not in
    the 2y or 30y buckets."""
    zero = Bond(face=100.0, annual_coupon_rate=0.0, maturity_years=10.0)
    kr = key_rate_dv01(zero, PARAMS)
    assert kr[10.0] == max(kr.values())
    others = kr[2.0] + kr[5.0] + kr[30.0]
    assert kr[10.0] > 3.0 * others  # dominant bucket


def test_barbell_vs_bullet_same_parallel_different_shape():
    """A 2y and a 30y bond load different key buckets even though each has all
    its risk at a single tenor — the whole point of the decomposition."""
    short = Bond(face=100.0, annual_coupon_rate=0.0, maturity_years=2.0)
    long = Bond(face=100.0, annual_coupon_rate=0.0, maturity_years=30.0)
    kr_short = key_rate_dv01(short, PARAMS)
    kr_long = key_rate_dv01(long, PARAMS)
    assert max(kr_short, key=kr_short.get) == 2.0
    assert max(kr_long, key=kr_long.get) == 30.0


def test_durations_sum_to_effective_duration():
    """Sum of key-rate durations equals -1/P dP/dy under a parallel shift
    (effective duration), which for a small bump is DV01/(P*1e-4)."""
    bond = Bond(face=100.0, annual_coupon_rate=0.04, maturity_years=15.0)
    from eur_curves.bonds import price

    krd = key_rate_durations(bond, PARAMS)
    p = price(bond, PARAMS)
    eff_dur = dv01(bond, PARAMS) / (p * 1e-4)
    assert sum(krd.values()) == pytest.approx(eff_dur, rel=1e-6)


def test_custom_key_tenors():
    bond = Bond(face=100.0, annual_coupon_rate=0.03, maturity_years=7.0)
    keys = (1.0, 3.0, 7.0, 15.0)
    kr = key_rate_dv01(bond, PARAMS, key_tenors=keys)
    assert set(kr.keys()) == set(keys)
    assert sum(kr.values()) == pytest.approx(dv01(bond, PARAMS), rel=1e-6)
