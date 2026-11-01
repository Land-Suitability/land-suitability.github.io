"""
Settlement, payments back to households, impact evaluation and learning signals.

  settle               delivery x contract price x grade premium, minus weight deductions for excess moisture
                       and foreign matter (shrink to the limit), minus the cooperative service fee
  pay_households       split a lot's net value by each household's kilograms in the lot (traceability)
  payment_timeliness   share of households paid within N days of delivery
  diff_in_diff         (pilot endline - baseline) - (comparison endline - baseline), bootstrap 95% CI
  yields_by_class      realised yield per suitability class (stage 01 recalibration check)
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .domain import Delivery, GradeTerms, HouseholdOutcome, HouseholdPayment, ImpactEstimate, Settlement


def settle(d: Delivery, contract_price_birr_t: float, terms: GradeTerms) -> Settlement:
    if d.weight_kg <= 0 or contract_price_birr_t <= 0:
        raise ValueError(f"{d.delivery_id}: weight and price must be positive")
    if d.grade not in terms.premium:
        raise KeyError(f"{d.delivery_id}: no premium defined for {d.grade}")
    # shrink: remove excess water and foreign matter from the payable weight
    excess = max(0.0, d.moisture - terms.moisture_limit) + max(0.0, d.foreign - terms.foreign_limit)
    payable = d.weight_kg * (1 - excess / 100)
    price = contract_price_birr_t * terms.premium[d.grade]
    gross = d.weight_kg / 1000 * price
    net_before_fee = payable / 1000 * price
    deductions = gross - net_before_fee
    fee = net_before_fee * terms.service_fee
    return Settlement(d.delivery_id, d.lot_id, payable, price, gross, deductions, fee, net_before_fee - fee)


def pay_households(s: Settlement, contributions_kg: dict[str, float], paid_on: dict[str, date | None]) -> list[HouseholdPayment]:
    """contributions_kg: household -> kg it contributed to the lot (from stage 09 lot -> plots -> households)."""
    total = sum(contributions_kg.values())
    if total <= 0:
        raise ValueError(f"Lot {s.lot_id}: no household contributions recorded")
    return [HouseholdPayment(h, s.lot_id, kg, s.net_birr * kg / total, paid_on.get(h)) for h, kg in contributions_kg.items()]


def payment_timeliness(payments: list[HouseholdPayment], delivered_on: dict[str, date], within_days: int = 14) -> float:
    ok = [p.paid_on is not None and (p.paid_on - delivered_on[p.lot_id]).days <= within_days for p in payments]
    return float(np.mean(ok)) if ok else 0.0


def diff_in_diff(rows: list[HouseholdOutcome], n_boot: int = 2000, seed: int = 0) -> ImpactEstimate:
    pilot = np.array([[r.baseline_birr, r.endline_birr] for r in rows if r.group == "pilot"])
    comp = np.array([[r.baseline_birr, r.endline_birr] for r in rows if r.group == "comparison"])
    if len(pilot) < 10 or len(comp) < 10:
        raise ValueError("Need at least 10 households in each group")
    dp, dc = pilot[:, 1] - pilot[:, 0], comp[:, 1] - comp[:, 0]
    effect = float(dp.mean() - dc.mean())
    rng = np.random.default_rng(seed)
    boots = [rng.choice(dp, len(dp)).mean() - rng.choice(dc, len(dc)).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return ImpactEstimate(effect, float(lo), float(hi), float(dp.mean()), float(dc.mean()))


def yields_by_class(records: list[tuple[str, float]]) -> dict[str, float]:
    """records: (suitability class from stage 01, realised t/ha). Returns mean yield per class."""
    acc = defaultdict(list)
    for cls, y in records:
        acc[cls].append(y)
    return {c: float(np.mean(v)) for c, v in sorted(acc.items())}
