"""
Domain model for Stage 07: Farm Implementation & Production.

Ubiquitous language
-------------------
Household       A farming household (pseudonymous ID only), its kebele and its willingness per crop.
HouseholdPlot   A plot the household holds use rights to, with suitability per crop option (stage 01).
PlotAssignment  The crop option and area a plot carries this season (cluster plan -> plot).
OperationTemplate  Agronomic steps of a crop relative to planting day (land preparation, planting, basal
                fertilizer, top dressing, weeding, irrigation rounds), each with a tolerance window.
PlannedOperation   One step on one plot with a target date and window.
FieldReport     What a development agent recorded: operation done, date, notes.
Adherence       Share of operations done inside their window; the basis for extension visit priority.

Analogy
-------
A school timetable for every plot. The plan says which subject (crop) each classroom (plot) teaches this
term, the timetable says when each lesson (operation) happens, and the teacher's register (field reports)
shows which lessons actually took place. The head teacher (extension) visits the classes falling behind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class OperationTemplate:
    option_id: str
    code: str              # "land_prep", "planting", "basal_fert", "top_dress", "weeding", "irrigation"
    offset_days: int       # relative to planting day
    tolerance_days: int    # done within +/- tolerance counts as on time
    repeat_every: int = 0  # for irrigation rounds
    repeat_until: int = 0  # offset of the last repeat


@dataclass
class HouseholdPlot:
    plot_id: str
    household_id: str
    kebele: str
    area_ha: float
    suitability: dict[str, float] = field(default_factory=dict)


@dataclass
class Household:
    household_id: str
    kebele: str
    willing: set[str] = field(default_factory=set)      # crop options the household agrees to grow
    plots: list[HouseholdPlot] = field(default_factory=list)


@dataclass(frozen=True)
class PlotAssignment:
    plot_id: str
    household_id: str
    kebele: str
    option_id: str
    area_ha: float
    suitability: float


@dataclass(frozen=True)
class PlannedOperation:
    plot_id: str
    kebele: str
    option_id: str
    code: str
    target: date
    tolerance_days: int


@dataclass(frozen=True)
class FieldReport:
    plot_id: str
    code: str
    done_on: date | None           # None = reported as not done
    agent_id: str = ""


@dataclass(frozen=True)
class VisitTask:
    plot_id: str
    kebele: str
    priority: float
    reasons: tuple[str, ...]
