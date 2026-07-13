"""eur-curves: a living EUR yield-curve lab on the ECB AAA Svensson curve."""

from .ecb import (
    SPOT_TENORS,
    CurveParams,
    fetch_params,
    fetch_params_history,
    fetch_published_spots,
    fetch_spot_history,
)
from .svensson import discount_factor, forward_rate, spot_rate

__version__ = "0.1.0"

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
    "__version__",
]
