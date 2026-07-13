"""Offline tests for the Svensson evaluation.

Reference values were computed independently with 50-digit ``decimal``
arithmetic (see comments) using the ECB parameter set published for
2026-07-10, so agreement is checked well past 10 significant digits.
"""

import math

import numpy as np
import pytest

from eur_curves.svensson import discount_factor, forward_rate, spot_rate

# ECB euro-area AAA Svensson parameters, 2026-07-10 (percent, cont. comp.)
PARAMS = (
    1.3035816676,  # beta0
    0.8859235246,  # beta1
    1.6170537131,  # beta2
    7.4347832397,  # beta3
    1.0113851993,  # tau1
    15.9471664368,  # tau2
)

# 50-digit Decimal references, truncated to double precision:
#   y(1)  = 2.5152077468236686406907814153094625411012234494501
#   y(5)  = 2.7430484744081603180164821005318522875810930132589
#   y(10) = 3.1085540183858361587787962457883591765798539919294
SPOT_REFERENCE = {
    1.0: 2.5152077468236686,
    5.0: 2.7430484744081603,
    10.0: 3.1085540183858362,
}

#   f(1)  = 2.6659034141717686035083785191040284110278390469858
#   f(5)  = 3.0705605814272205312966761428070912116680086495572
#   f(10) = 3.7947378618061006893205119256565454091085654023275
FORWARD_REFERENCE = {
    1.0: 2.6659034141717686,
    5.0: 3.0705605814272205,
    10.0: 3.7947378618061007,
}

#   P(10) = 0.73281983260901771633148013264678557270155299719443
DISCOUNT_10Y_REFERENCE = 0.7328198326090177


@pytest.mark.parametrize("t", sorted(SPOT_REFERENCE))
def test_spot_rate_matches_hand_computed(t):
    assert spot_rate(t, *PARAMS) == pytest.approx(SPOT_REFERENCE[t], rel=1e-13)


@pytest.mark.parametrize("t", sorted(FORWARD_REFERENCE))
def test_forward_rate_matches_hand_computed(t):
    assert forward_rate(t, *PARAMS) == pytest.approx(FORWARD_REFERENCE[t], rel=1e-13)


def test_spot_rate_t0_limit_is_b0_plus_b1():
    b0, b1 = PARAMS[0], PARAMS[1]
    assert spot_rate(0.0, *PARAMS) == pytest.approx(b0 + b1, rel=1e-15)
    # continuity: tiny t stays next to the analytic limit
    assert spot_rate(1e-9, *PARAMS) == pytest.approx(b0 + b1, abs=1e-8)


def test_forward_rate_t0_limit_is_b0_plus_b1():
    b0, b1 = PARAMS[0], PARAMS[1]
    assert forward_rate(0.0, *PARAMS) == pytest.approx(b0 + b1, rel=1e-15)


def test_forward_is_derivative_of_t_times_spot():
    """f(t) = d/dt [t * y(t)], checked against a central difference."""
    h = 1e-6
    for t in (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0):
        ty = lambda u: u * spot_rate(u, *PARAMS)  # noqa: E731
        numerical = (ty(t + h) - ty(t - h)) / (2 * h)
        assert forward_rate(t, *PARAMS) == pytest.approx(numerical, abs=1e-6)


def test_discount_factor_matches_hand_computed():
    assert discount_factor(10.0, *PARAMS) == pytest.approx(DISCOUNT_10Y_REFERENCE, rel=1e-13)


def test_discount_factor_roundtrip():
    """Inverting P(t) = exp(-y t / 100) recovers the spot rate."""
    for t in (0.25, 1.0, 5.0, 10.0, 30.0):
        p = discount_factor(t, *PARAMS)
        recovered = -100.0 / t * math.log(p)
        assert recovered == pytest.approx(spot_rate(t, *PARAMS), rel=1e-12)


def test_discount_factor_at_zero_is_one():
    assert discount_factor(0.0, *PARAMS) == 1.0


def test_array_inputs_match_scalars():
    t = np.array([0.0, 0.25, 1.0, 5.0, 10.0, 30.0])
    spot_vec = spot_rate(t, *PARAMS)
    fwd_vec = forward_rate(t, *PARAMS)
    df_vec = discount_factor(t, *PARAMS)
    assert spot_vec.shape == fwd_vec.shape == df_vec.shape == t.shape
    for i, ti in enumerate(t):
        assert spot_vec[i] == pytest.approx(spot_rate(float(ti), *PARAMS), rel=1e-15)
        assert fwd_vec[i] == pytest.approx(forward_rate(float(ti), *PARAMS), rel=1e-15)
        assert df_vec[i] == pytest.approx(discount_factor(float(ti), *PARAMS), rel=1e-15)


def test_scalar_return_types_are_floats():
    assert isinstance(spot_rate(5.0, *PARAMS), float)
    assert isinstance(forward_rate(5.0, *PARAMS), float)
    assert isinstance(discount_factor(5.0, *PARAMS), float)
