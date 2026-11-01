"""
Domain model for Stage 12: Market Distribution, Customer Network and the Learning Loop.

Ubiquitous language
-------------------
Delivery          Lots (stage 09) delivered to a buyer under a contract (stage 05), with the weight and quality
                  measured at the buyer's gate.
Settlement        The money due for a delivery: contract price rule x grade premium, minus quality deductions
                  and the cooperative service fee.
HouseholdPayment  Each household's share of a settled lot, in proportion to the kilograms its plots contributed
                  (traceability from lot -> plots -> households), with the date paid.
HouseholdOutcome  Net income per household at baseline and endline, for pilot and comparison kebeles.
ImpactEstimate    Difference-in-differences effect on income with a confidence interval.
LearningSignal    What goes back up the chain: realised prices (05), yields by suitability class (01),
                  buyer feedback and contract performance (05, 09).

Analogy
-------
A relay race where the baton is information. Grain runs forward from field to buyer; money runs back from buyer
to household; and the lessons (prices, yields, quality) run all the way back to the start line so next
season's plan starts from what really happened, not from what was assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class GradeTerms:
    premium: dict[str, float]          # grade -> price multiplier, e.g. {"grade 1": 1.05, "grade 2": 1.0}
    moisture_limit: float              # % above which a weight deduction applies
    foreign_limit: float               # % above which a weight deduction applies
    service_fee: float = 0.03          # cooperative service fee on gross value


@dataclass(frozen=True)
class Delivery:
    delivery_id: str
    contract_id: str
    lot_id: str
    delivered_on: date
    weight_kg: float
    moisture: float
    foreign: float
    grade: str


@dataclass(frozen=True)
class Settlement:
    delivery_id: str
    lot_id: str
    payable_kg: float
    price_birr_t: float
    gross_birr: float
    deductions_birr: float
    fee_birr: float
    net_birr: float


@dataclass(frozen=True)
class HouseholdPayment:
    household_id: str
    lot_id: str
    kg: float
    amount_birr: float
    paid_on: date | None


@dataclass
class HouseholdOutcome:
    household_id: str
    group: str                         # "pilot" | "comparison"
    baseline_birr: float
    endline_birr: float


@dataclass(frozen=True)
class ImpactEstimate:
    effect_birr: float
    low95: float
    high95: float
    pilot_change: float
    comparison_change: float


@dataclass
class LearningSignal:
    yields_by_class: dict[str, float] = field(default_factory=dict)
    realised_price_birr_t: float | None = None
    on_time_payment_share: float | None = None
    buyer_rating: float | None = None
