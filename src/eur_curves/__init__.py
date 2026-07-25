"""eur-curves: a living EUR yield-curve lab on the ECB AAA Svensson curve."""

from .bonds import (
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
from .ecb import (
    SPOT_TENORS,
    CurveParams,
    fetch_params,
    fetch_params_history,
    fetch_published_spots,
    fetch_spot_history,
)
from .svensson import discount_factor, forward_rate, spot_rate

__version__ = "0.2.0"

__all__ = [
    "CurveParams",
    "SPOT_TENORS",
    "discount_factor",
    "fetch_params",
    "fetch_params_history",
    "fetch_published_spots",
    "fetch_spot_history",
    "forward_rate",
    "spot_rate",
    "Bond",
    "parallel_shift",
    "price",
    "par_coupon",
    "yield_to_maturity",
    "dv01",
    "macaulay_duration",
    "modified_duration",
    "convexity",
    "__version__",
]
