"""
Market analytics for Stage 05.

  fit_price_model      log(price) = a + b * t + month effects  (least squares; trend captures inflation)
  forecast             harvest-time price with an 80% prediction interval (residual spread)
  contract_outcomes    Monte Carlo of a contract against simulated delivery-time market prices:
                         farmers side-sell when the market pays clearly more than the contract;
                         buyers walk away when the market is clearly cheaper than the contract.
  demand_signal        contracted minimum + absorbable spot volume -> DemandSignal for stage 04
"""
from __future__ import annotations

import numpy as np

from .domain import DemandSignal, OfftakeContract, PriceForecast, PriceObservation, PriceRule

Z80 = 1.2816


class PriceModel:
    def __init__(self, coef: np.ndarray, resid_sd: float, t0: int, product: str, market: str):
        self.coef, self.resid_sd, self.t0, self.product, self.market = coef, resid_sd, t0, product, market

    def _x(self, year: int, month: int) -> np.ndarray:
        t = (year * 12 + month - 1) - self.t0
        x = np.zeros(13)
        x[0], x[1] = 1.0, t / 12.0
        if month > 1:
            x[month] = 1.0           # month 1 (January) is the baseline
        return x

    def seasonal_index(self) -> np.ndarray:
        """Price in each month relative to the annual mean (trend removed)."""
        eff = np.concatenate([[0.0], self.coef[2:]])
        rel = np.exp(eff)
        return rel / rel.mean()

    @property
    def annual_trend(self) -> float:
        return float(np.exp(self.coef[1]) - 1)


def fit_price_model(obs: list[PriceObservation]) -> PriceModel:
    if len(obs) < 24:
        raise ValueError(f"Need at least 24 monthly observations, got {len(obs)}")
    products = {(o.product, o.market) for o in obs}
    if len(products) != 1:
        raise ValueError(f"Fit one product and market at a time, got {products}")
    t0 = min(o.year * 12 + o.month - 1 for o in obs)
    model = PriceModel(np.zeros(13), 0.0, t0, obs[0].product, obs[0].market)
    X = np.array([model._x(o.year, o.month) for o in obs])
    y = np.log([o.price_birr_t for o in obs])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    model.coef, model.resid_sd = coef, float(resid.std(ddof=13))
    return model


def forecast(model: PriceModel, year: int, month: int, issued: tuple[int, int] | None = None,
             shock_sd_per_month: float = 0.045) -> PriceForecast:
    """
    Median from trend + season. Uncertainty = residual noise plus a random-walk shock that grows with
    the horizon (inflation, exchange-rate and policy surprises): sd^2 = resid^2 + h * shock^2.
    `issued` is the (year, month) the forecast is made, e.g. when a contract is signed before planting.
    """
    mu = float(model._x(year, month) @ model.coef)
    h = 0 if issued is None else (year * 12 + month) - (issued[0] * 12 + issued[1])
    if h < 0:
        raise ValueError("Forecast month is before the issue month")
    sd = float(np.sqrt(model.resid_sd ** 2 + h * shock_sd_per_month ** 2))
    return PriceForecast(model.product, model.market, year, month, float(np.exp(mu)),
                         float(np.exp(mu - Z80 * sd)), float(np.exp(mu + Z80 * sd)))


def contract_outcomes(contract: OfftakeContract, fc: PriceForecast, n: int = 20_000, side_sell_gap: float = 0.15,
                      walk_away_gap: float = 0.15, seed: int = 0) -> dict:
    """
    Simulate delivery-time market prices (lognormal around the forecast) and apply behaviour rules.
    An advance payment raises the farmers' side-selling threshold by the advance share.
    """
    if fc.median <= 0:
        raise ValueError("Forecast median must be positive")
    rng = np.random.default_rng(seed)
    sd = (np.log(fc.high80) - np.log(fc.low80)) / (2 * Z80)
    market = np.exp(np.log(fc.median) + rng.normal(0, sd, n))
    paid = contract.rule.price(market)
    side_sell = market > paid * (1 + side_sell_gap + contract.advance_share)
    walk_away = market < paid * (1 - walk_away_gap)
    honoured = ~(side_sell | walk_away)
    farmer_price = np.where(honoured, paid, market)     # if the contract breaks, farmers sell at market
    return {
        "honoured": float(honoured.mean()), "side_sell": float(side_sell.mean()), "walk_away": float(walk_away.mean()),
        "farmer_price_mean": float(farmer_price.mean()), "farmer_price_p10": float(np.percentile(farmer_price, 10)),
        "buyer_cost_mean": float(np.where(honoured, paid, market).mean()),
    }


def demand_signal(contracts: list[OfftakeContract], product: str, spot_absorbable_t: float,
                  planning_price: float) -> DemandSignal:
    vol = sum(c.volume_t for c in contracts if c.product == product)
    if vol < 0 or spot_absorbable_t < 0:
        raise ValueError("Volumes must be non-negative")
    return DemandSignal(product, min_t=vol, max_t=vol + spot_absorbable_t, price_birr_t=planning_price)


def band_around(fc: PriceForecast, width: float = 0.15) -> PriceRule:
    from .domain import RuleKind
    return PriceRule(RuleKind.BAND, floor=fc.median * (1 - width), ceiling=fc.median * (1 + width))
