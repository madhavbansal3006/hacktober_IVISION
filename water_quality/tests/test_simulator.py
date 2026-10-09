import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator import generate_readings
from src.wqi import validate_observation

MWS_ID = "g_mws.240575"
MWS_CODE = "4D4F2m3"


# 7. Simulator output -----------------------------------------------------------
def test_simulator_generates_requested_count():
    readings = generate_readings(MWS_ID, MWS_CODE, count=5, seed=42)
    assert len(readings) == 5


def test_simulator_output_has_required_fields_and_is_valid():
    readings = generate_readings(MWS_ID, MWS_CODE, count=3, seed=1)
    for reading in readings:
        for field in ("id", "MWS", "timestamp", "ph", "tds", "turbidity",
                      "temperature", "source"):
            assert field in reading
        # Simulated values should always pass validation.
        validate_observation(reading)


# 8. Simulator source == "simulation" --------------------------------------------
def test_simulator_source_is_always_simulation():
    readings = generate_readings(MWS_ID, MWS_CODE, count=10, seed=7)
    assert all(r["source"] == "simulation" for r in readings)


# 9. MWS id preservation ------------------------------------------------------------
def test_simulator_preserves_mws_id_and_code():
    readings = generate_readings(MWS_ID, MWS_CODE, count=4, seed=3)
    assert all(r["id"] == MWS_ID for r in readings)
    assert all(r["MWS"] == MWS_CODE for r in readings)


# 10. Deterministic output when seed is fixed -----------------------------------------
def test_simulator_is_deterministic_with_fixed_seed():
    readings_a = generate_readings(MWS_ID, MWS_CODE, count=5, seed=99,
                                    start_time=None)
    readings_b = generate_readings(MWS_ID, MWS_CODE, count=5, seed=99,
                                    start_time=None)
    # Strip timestamps (which depend on wall-clock 'now' when start_time is
    # None) before comparing, since only the sampled values must match.
    values_a = [{k: v for k, v in r.items() if k != "timestamp"} for r in readings_a]
    values_b = [{k: v for k, v in r.items() if k != "timestamp"} for r in readings_b]
    assert values_a == values_b


def test_simulator_different_seeds_generally_differ():
    readings_a = generate_readings(MWS_ID, MWS_CODE, count=5, seed=1)
    readings_b = generate_readings(MWS_ID, MWS_CODE, count=5, seed=2)
    assert readings_a != readings_b
