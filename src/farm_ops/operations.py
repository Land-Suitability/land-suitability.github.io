"""
From cluster plan to plots, calendars, adherence and extension visits.

  assign_plots        cluster target hectares per option -> plot assignments. Plots are offered to options
                      in order of suitability, only to willing households, until each target is met.
  build_calendar      operation templates x assignments -> dated planned operations
  adherence           planned operations vs field reports -> on-time share per plot and per operation type
  prioritise_visits   rank plots for extension visits by risk (missed or late steps, area, value at stake)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .domain import FieldReport, Household, OperationTemplate, PlannedOperation, PlotAssignment, VisitTask


def assign_plots(households: list[Household], targets_ha: dict[str, float], min_suitability: float = 0.5
                 ) -> tuple[list[PlotAssignment], dict[str, float]]:
    """
    Greedy by COMPARATIVE ADVANTAGE: a plot goes first to the option it suits better than the household's
    other willing options (like giving each player the position they play best relative to the others),
    then by suitability. Each plot carries one option. Returns assignments and unmet hectares per option.
    """
    pairs = []
    for h in households:
        for p in h.plots:
            ok = {o: p.suitability.get(o, 0.0) for o in targets_ha if o in h.willing and p.suitability.get(o, 0.0) >= min_suitability}
            for opt, s in ok.items():
                others = [v for o, v in ok.items() if o != opt]
                advantage = s - max(others) if others else s
                pairs.append((advantage, s, p.area_ha, p, h, opt))
    pairs.sort(key=lambda t: (-t[0], -t[1], -t[2]))
    left = dict(targets_ha)
    used, out = set(), []
    for _adv, s, area, p, h, opt in pairs:
        if p.plot_id in used or left[opt] <= 1e-9:
            continue
        used.add(p.plot_id)
        out.append(PlotAssignment(p.plot_id, h.household_id, h.kebele, opt, area, s))
        left[opt] -= area
    gaps = {k: max(0.0, v) for k, v in left.items()}
    return out, gaps


def build_calendar(assignments: list[PlotAssignment], templates: list[OperationTemplate],
                   planting: dict[str, date]) -> list[PlannedOperation]:
    ops = []
    for a in assignments:
        if a.option_id not in planting:
            raise KeyError(f"No planting date for {a.option_id}")
        day0 = planting[a.option_id]
        for t in (t for t in templates if t.option_id == a.option_id):
            offsets = [t.offset_days]
            if t.repeat_every:
                offsets = list(range(t.offset_days, t.repeat_until + 1, t.repeat_every))
            for off in offsets:
                ops.append(PlannedOperation(a.plot_id, a.kebele, a.option_id, t.code, day0 + timedelta(days=off), t.tolerance_days))
    return ops


def adherence(ops: list[PlannedOperation], reports: list[FieldReport], as_of: date) -> dict:
    """Only operations whose window has closed by `as_of` are scored."""
    rep = defaultdict(list)
    for r in reports:
        rep[(r.plot_id, r.code)].append(r)
    by_plot, by_code, by_kebele_code = defaultdict(list), defaultdict(list), defaultdict(list)
    late_or_missed = defaultdict(list)
    seen = defaultdict(int)
    for op in sorted(ops, key=lambda o: o.target):
        if op.target + timedelta(days=op.tolerance_days) > as_of:
            continue
        k = (op.plot_id, op.code)
        i = seen[k]
        seen[k] += 1
        r = rep[k][i] if i < len(rep[k]) else None
        ok = r is not None and r.done_on is not None and abs((r.done_on - op.target).days) <= op.tolerance_days
        by_plot[op.plot_id].append(ok)
        by_code[op.code].append(ok)
        by_kebele_code[(op.kebele, op.code)].append(ok)
        if not ok:
            late_or_missed[op.plot_id].append(op.code if r and r.done_on else f"{op.code} missing")
    share = lambda xs: sum(xs) / len(xs) if xs else None  # noqa: E731
    return {"plot": {k: share(v) for k, v in by_plot.items()}, "code": {k: share(v) for k, v in by_code.items()},
            "kebele_code": {k: share(v) for k, v in by_kebele_code.items()}, "issues": dict(late_or_missed)}


def prioritise_visits(assignments: list[PlotAssignment], adh: dict, value_birr_ha: dict[str, float],
                      capacity: int) -> list[VisitTask]:
    """Risk = (1 - adherence) x area x value per ha, plus a bonus for missing (not just late) steps."""
    if capacity < 0:
        raise ValueError("capacity must be >= 0")
    tasks = []
    for a in assignments:
        score = adh["plot"].get(a.plot_id)
        if score is None:
            continue
        issues = adh["issues"].get(a.plot_id, [])
        missing = sum("missing" in i for i in issues)
        risk = (1 - score) * a.area_ha * value_birr_ha.get(a.option_id, 0) / 1000 + 5 * missing
        if risk > 0:
            tasks.append(VisitTask(a.plot_id, a.kebele, round(risk, 1), tuple(issues)))
    return sorted(tasks, key=lambda t: -t.priority)[:capacity]
