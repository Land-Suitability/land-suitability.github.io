"""Tests for water availability mapping. Run: python3 -m pytest tests  (or python3 tests/test_mapping.py)"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from water_res import (AccessClass as A, GwClass, MappingRules, WaterPoint, d8_receivers, fill_depressions,  # noqa: E402
                       flow_accumulation, groundwater_potential, load_handoff, stream_flow_m3, water_access)

FLAT12 = tuple([1000.0] * 12)


def test_fill_removes_a_pit_and_never_lowers():
    z = np.full((5, 5), 10.0); z[2, 2] = 5.0
    f = fill_depressions(z)
    assert f[2, 2] >= 10.0 and np.all(f >= z)


def test_d8_on_a_tilted_plane_flows_downhill_and_accumulates():
    z = np.tile(np.arange(6, 0, -1, dtype=float)[:, None], (1, 4)) * 10   # high in the north, low in the south
    f = fill_depressions(z)
    rec = d8_receivers(f)
    acc = flow_accumulation(f, rec)
    assert rec[0] in (4, 5)                       # top-left drains to the next row down
    assert acc[-1].sum() == z.size                # every cell ends in the bottom row


def test_stream_flow_units():
    q = stream_flow_m3(np.array([[1.0]]), tuple([1.0] * 12))
    assert q.shape == (12, 1, 1) and q[0, 0, 0] == 1000.0     # 1 mm over 1 km2 = 1000 m3


def test_groundwater_weights_and_ranges_are_checked():
    ones = np.ones((2, 2))
    f = {k: ones * 0.5 for k in MappingRules().gw_weights}
    idx, cls = groundwater_potential(f)
    assert np.allclose(idx, 0.5) and (cls == GwClass.MODERATE).all()
    for bad in (lambda: groundwater_potential({**f, "slope": ones * 2}),
                lambda: groundwater_potential({k: v for k, v in f.items() if k != "geology"}),
                lambda: MappingRules(gw_weights={"geology": 0.5})):
        try:
            bad()
        except (ValueError, KeyError):
            continue
        raise AssertionError("bad groundwater input should raise")


def _access(field_z, src_z, src_dist_cells, gw=GwClass.LOW, cell_m=100.0):
    n = src_dist_cells + 1
    elev = np.full((1, n), float(field_z)); elev[0, n - 1] = src_z
    avail = np.zeros((1, n), bool); avail[0, 0] = True
    pts = [WaterPoint("S1", "stream", (0, n - 1), float(src_z), FLAT12)]
    return water_access(avail, elev, pts, np.full((1, n), int(gw)), np.full((1, n), 50.0), cell_m)


def test_gravity_when_the_source_is_high_enough():
    m = _access(field_z=100, src_z=110, src_dist_cells=10)       # 1 km: needs 100 + 2 + 2 = 104 m
    assert m.access[0, 0] == A.GRAVITY and m.source_id[0, 0] == "S1"


def test_pumped_when_the_source_is_lower_but_close():
    m = _access(field_z=100, src_z=90, src_dist_cells=5)         # 0.5 km, 10 m lift
    assert m.access[0, 0] == A.PUMPED and abs(m.lift_m[0, 0] - 10) < 1e-9


def test_groundwater_then_harvest_when_no_surface_source_reaches():
    far_high_gw = _access(field_z=100, src_z=40, src_dist_cells=30, gw=GwClass.HIGH)
    far_low_gw = _access(field_z=100, src_z=40, src_dist_cells=30, gw=GwClass.LOW)
    assert far_high_gw.access[0, 0] == A.GROUNDWATER and far_low_gw.access[0, 0] == A.HARVEST_ONLY
    gid = far_high_gw.source_id[0, 0]
    assert far_high_gw.points[gid].sustainable_m3[0] == 50.0


def test_the_bigger_source_wins_over_the_nearer_one():
    elev = np.array([[100.0, 0.0, 0.0, 0.0, 0.0]])
    avail = np.array([[True, False, False, False, False]])
    pts = [WaterPoint("SPRING", "spring", (0, 1), 120.0, tuple([10.0] * 12)),
           WaterPoint("STREAM", "stream", (0, 4), 120.0, tuple([5000.0] * 12))]
    m = water_access(avail, elev, pts, np.ones((1, 5), int), np.zeros((1, 5)), 100.0)
    assert m.access[0, 0] == A.GRAVITY and m.source_id[0, 0] == "STREAM"


def test_unavailable_land_is_not_assessed():
    m = _access(field_z=100, src_z=110, src_dist_cells=10)
    assert (m.access[0, 1:] == A.NOT_ASSESSED).all()


def test_leanest_month_per_hectare():
    m = _access(field_z=100, src_z=110, src_dist_cells=10)
    month, per_ha = m.leanest_month_m3_per_ha()["S1"]
    assert month == "Jan" and per_ha == 1000.0       # 1 ha cell (100 m) depends on S1


def test_intakes_on_one_stream_share_its_water():
    elev = np.array([[100.0, 100.0, 0.0, 0.0]])
    avail = np.array([[True, True, False, False]])
    up = WaterPoint("UP", "stream", (0, 2), 110.0, tuple([400.0] * 12), group="BASIN-1")
    down = WaterPoint("DOWN", "stream", (0, 3), 108.0, tuple([1000.0] * 12), group="BASIN-1")
    m = water_access(avail, elev, [up, down], np.ones((1, 4), int), np.zeros((1, 4)), 100.0)
    bodies = m.water_bodies()
    assert list(bodies) == ["BASIN-1"]
    assert bodies["BASIN-1"]["sustainable_m3"][0] == 1000.0     # the outlet flow, not 400 + 1000


def test_handoff_contract_is_enforced():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "h.json"
        p.write_text(json.dumps({"contract": "something.else", "version": "0.1"}))
        try:
            load_handoff(p)
        except ValueError:
            return
    raise AssertionError("a wrong contract should be rejected")


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  [PASS] {name}")
            except Exception as e:  # debugging block: report and continue
                failed += 1; print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
