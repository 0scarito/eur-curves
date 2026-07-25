# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-25

### Added
- `eur_curves.bonds` — a fixed-income analytics layer priced off a fitted
  Svensson `CurveParams`:
  - `Bond` dataclass for bullet fixed-coupon bonds (face, annual coupon rate,
    maturity, coupons per year) with a `cashflows()` schedule.
  - `price` — dirty price by discounting every cashflow with the curve's
    continuous-compounding discount factor.
  - `yield_to_maturity` — effective-annual YTM via Brent's method
    (`sum(cf * (1 + y) ** -t) == price`).
  - `dv01` — price change for a ±1 bp parallel shift, computed as an **exact**
    curve shift (`beta0` enters the spot rate additively).
  - `macaulay_duration`, `modified_duration` (`= macaulay / (1 + y)`), and
    `convexity` from the discounted cashflows.
  - `par_coupon` (closed-form par yield) and `parallel_shift` helpers.
- `plots.plot_bond_ladder` — prices a ladder of par bonds across maturities and
  charts DV01 (bars) and modified duration (line) vs maturity; `refresh.py` now
  also writes `charts/bonds.png`.
- New offline test module `tests/test_bonds.py` (par-bond round trip, DV01 vs a
  finite-difference reprice, duration relationships, positive convexity, and
  price monotonicity in yield).
- `scipy>=1.10` runtime dependency (Brent root-finder for YTM).
- `CHANGELOG.md`.

### Notes
- Bonds are discounted off the euro-area AAA government curve only — no credit
  spread and no OIS/collateral (€STR) discounting. DV01 is a single parallel
  shift; key-rate durations are a roadmap item.

## [0.1.0] - 2026-07-13

### Added
- Initial release: the Svensson (1994) model (`spot_rate`, `discount_factor`,
  `forward_rate`), the ECB Data Portal client (`ecb`), charts, and the daily
  `refresh.py` that rebuilds the curve and validates it against the ECB's own
  published spot rates to 0.5 bp.

[0.2.0]: https://github.com/0scarito/eur-curves/releases/tag/v0.2.0
[0.1.0]: https://github.com/0scarito/eur-curves/releases/tag/v0.1.0
