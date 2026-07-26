"""Key-rate (partial) durations: where a bond's rate risk actually sits.

Parallel DV01 (see :func:`eur_curves.bonds.dv01`) answers "what if the whole
curve moves 1bp?" — but a 10-year bond and a barbell of 2s and 30s can share
the same parallel DV01 while reacting completely differently to a steepening.
Key-rate durations decompose the risk by maturity bucket.

Method (Ho 1992, "Key Rate Durations"): pick a set of key tenors; perturb the
spot curve by a **triangular (tent) bump** centred on one key tenor, ramping
linearly to zero at the neighbouring keys; reprice; repeat per key. The tents
form a *partition of unity* — they sum to 1 at every maturity — so bumping all
keys at once is exactly a parallel shift, and therefore

    sum of the key-rate DV01s == the parallel DV01

to numerical precision. That identity is the module's headline test.

The bump is applied additively to the Svensson spot rate (percent), so it needs
no re-fit: ``P = sum(cf · exp(-(y(t) + bump(t))/100 · t))``.
"""

from __future__ import annotations

import numpy as np

from .bonds import Bond, dv01
from .ecb import CurveParams
from .svensson import spot_rate

DEFAULT_KEY_TENORS: tuple[float, ...] = (2.0, 5.0, 10.0, 30.0)


def tent_weight(t, key_tenors: np.ndarray, i: int) -> np.ndarray:
    """Triangular weight for key ``i``: 1 at ``key_tenors[i]``, 0 at neighbours.

    The end keys are flat beyond the last knot (weight 1 for ``t`` below the
    first / above the last key), so the weights partition unity over ``t >= 0``.
    """
    t = np.asarray(t, dtype=float)
    keys = np.asarray(key_tenors, dtype=float)
    k = keys[i]
    left = keys[i - 1] if i > 0 else None
    right = keys[i + 1] if i < len(keys) - 1 else None

    if left is None:  # leftmost: flat 1 below k, ramp down to the next key
        return np.where(t <= k, 1.0, np.clip((right - t) / (right - k), 0.0, 1.0))
    if right is None:  # rightmost: ramp up from previous key, flat 1 above k
        return np.where(t >= k, 1.0, np.clip((t - left) / (k - left), 0.0, 1.0))
    up = np.clip((t - left) / (k - left), 0.0, 1.0)
    down = np.clip((right - t) / (right - k), 0.0, 1.0)
    w = np.minimum(up, down)
    return np.where((t < left) | (t > right), 0.0, w)


def _price_with_bump(bond: Bond, params: CurveParams, bump_percent) -> float:
    """Price the bond discounting at ``y(t) + bump_percent(t)`` (percent)."""
    times, amounts = bond.cashflows()
    y = np.asarray(spot_rate(times, *params.as_tuple()), dtype=float)
    y_bumped = y + np.asarray(bump_percent(times), dtype=float)
    dfs = np.exp(-y_bumped / 100.0 * times)
    return float(np.sum(amounts * dfs))


def key_rate_dv01(
    bond: Bond,
    params: CurveParams,
    key_tenors: tuple[float, ...] | np.ndarray = DEFAULT_KEY_TENORS,
    shift_bp: float = 1.0,
) -> dict[float, float]:
    """Key-rate DV01s: price change per ``shift_bp`` bump at each key tenor.

    Central-differenced (``(P(-bump) - P(+bump)) / 2``), so a positive value is
    the price drop for a +``shift_bp`` bump at that tenor — the same sign
    convention as :func:`eur_curves.bonds.dv01`. The sum over keys equals the
    parallel DV01.
    """
    keys = np.asarray(key_tenors, dtype=float)
    out: dict[float, float] = {}
    for i, k in enumerate(keys):
        def bump(t, i=i, sign=1.0):
            return sign * shift_bp * 0.01 * tent_weight(t, keys, i)
        up = _price_with_bump(bond, params, lambda t, i=i: bump(t, i, +1.0))
        down = _price_with_bump(bond, params, lambda t, i=i: bump(t, i, -1.0))
        out[float(k)] = (down - up) / 2.0
    return out


def key_rate_durations(
    bond: Bond,
    params: CurveParams,
    key_tenors: tuple[float, ...] | np.ndarray = DEFAULT_KEY_TENORS,
) -> dict[float, float]:
    """Key-rate durations (years): ``KRD_k = KR01_k / (P · 1e-4)``.

    Each is the fractional price sensitivity to a 1bp bump localised at key
    ``k``; they sum to the (modified-equivalent) effective duration under a
    parallel shift.
    """
    from .bonds import price

    p = price(bond, params)
    kr01 = key_rate_dv01(bond, params, key_tenors, shift_bp=1.0)
    return {k: v / (p * 1e-4) for k, v in kr01.items()}


def parallel_dv01_from_keys(
    bond: Bond,
    params: CurveParams,
    key_tenors: tuple[float, ...] | np.ndarray = DEFAULT_KEY_TENORS,
) -> tuple[float, float]:
    """``(sum of key-rate DV01s, parallel DV01)`` — the partition-of-unity check.

    The two agree to numerical precision because the tent weights sum to 1 at
    every maturity, so bumping every key equals a parallel shift.
    """
    return sum(key_rate_dv01(bond, params, key_tenors).values()), dv01(bond, params)
