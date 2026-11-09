"""Tests for land availability. Run: python3 -m pytest tests  (or python3 tests/test_availability.py)"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from land_intel import (AvailabilityRules, AvailabilityStatus as S, AvailableLand, LandCover as C, Reason,  # noqa: E402
                        assess_availability, available_and_suitable)


def grid(cover, slope=5.0, protected=False, grazing=False, road=1.0):
    cover = np.array(cover, dtype=int)
    full = lambda v: np.full(cover.shape, v) if np.isscalar(v) else np.array(v)
    return assess_availability(cover, full(slope).astype(float), full(protected).astype(bool), full(grazing).astype(bool),
                               full(road).astype(float), AvailabilityRules(cell_size_m=100))


def test_cropland_is_in_use_and_open_land_is_expandable():
    r = grid([[C.CROPLAND, C.GRASSLAND, C.SHRUBLAND]])
    assert r.status.tolist() == [[S.IN_USE, S.EXPANDABLE, S.EXPANDABLE]]


def test_hard_covers_are_excluded_with_their_reason():
    r = grid([[C.FOREST, C.BUILT_UP, C.BARE]])
    assert (r.status == S.EXCLUDED).all()
    assert r.reasons[0, 0] & Reason.FOREST and r.reasons[0, 1] & Reason.BUILT_UP and r.reasons[0, 2] & Reason.BARE


def test_protected_beats_good_cropland():
    r = grid([[C.CROPLAND]], protected=[[True]])
    assert r.status[0, 0] == S.EXCLUDED and r.reasons[0, 0] & Reason.PROTECTED


def test_slope_bands():
    r = grid([[C.GRASSLAND, C.GRASSLAND, C.GRASSLAND]], slope=[[10, 20, 35]])
    assert r.status.tolist() == [[S.EXPANDABLE, S.CONDITIONAL, S.EXCLUDED]]
    assert r.reasons[0, 1] & Reason.TERRACES_NEEDED and r.reasons[0, 2] & Reason.VERY_STEEP


def test_existing_cropland_on_moderate_slope_stays_in_use_with_a_note():
    r = grid([[C.CROPLAND]], slope=[[20]])
    assert r.status[0, 0] == S.IN_USE and r.reasons[0, 0] & Reason.TERRACES_NEEDED


def test_grazing_and_remoteness_make_open_land_conditional():
    r = grid([[C.GRASSLAND, C.GRASSLAND]], grazing=[[True, False]], road=[[1, 9]])
    assert r.status.tolist() == [[S.CONDITIONAL, S.CONDITIONAL]]
    assert r.reasons[0, 0] & Reason.COMMUNAL_GRAZING and r.reasons[0, 1] & Reason.REMOTE


def test_water_buffer_excludes_the_bank_but_not_beyond():
    r = grid([[C.WATER, C.CROPLAND, C.CROPLAND]])          # 100 m cells, 30 m buffer -> one cell
    assert r.status.tolist() == [[S.EXCLUDED, S.EXCLUDED, S.IN_USE]]
    assert r.reasons[0, 1] & Reason.WATER_BUFFER


def test_hectares_add_up():
    r = grid([[C.CROPLAND, C.GRASSLAND], [C.FOREST, C.SHRUBLAND]])
    ha = r.hectares()
    assert abs(sum(ha.values()) - 4 * 1.0) < 1e-9       # 100 m cells = 1 ha each


def test_available_and_suitable_counts_only_open_statuses():
    r = grid([[C.CROPLAND, C.GRASSLAND, C.FOREST]])
    ranks = np.array([[3, 2, 3]])
    out = available_and_suitable(r, ranks)
    assert out["S1"] == 1.0 and out["S2"] == 1.0          # the S1 forest cell is not counted


def test_bad_inputs_are_rejected():
    for bad in (lambda: grid([[99]]),
                lambda: grid([[C.CROPLAND]], slope=[[np.nan]]),
                lambda: AvailabilityRules(terrace_slope_pct=40, max_slope_pct=30)):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("invalid input should raise ValueError")


def test_available_land_plannable():
    a = AvailableLand("A", {"IN_USE": 10}, {"teff": {"S1": 4, "S2": 3, "S3": 2}})
    assert a.plannable_ha("teff") == 7
    try:
        a.plannable_ha("maize")
    except KeyError:
        return
    raise AssertionError("unknown crop should raise KeyError")


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  [PASS] {name}")
            except Exception as e:  # debugging block: report and continue
                failed += 1; print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
