import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.wqi import (
    ObservationValidationError,
    calculate_wqi,
    classify_wqi,
    evaluate_observation,
    validate_observation,
)


def make_observation(**overrides):
    base = {
        "id": "g_mws.240575",
        "MWS": "4D4F2m3",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "ph": 7.0,
        "tds": 0.0,
        "turbidity": 0.0,
        "temperature": 25.0,
        "source": "simulation",
    }
    base.update(overrides)
    return base


# 1. WQI calculation ---------------------------------------------------------
def test_wqi_calculation_ideal_values_gives_zero():
    """An observation matching every 'ideal' value should score WQI == 0."""
    obs = make_observation(ph=7.0, tds=0.0, turbidity=0.0, temperature=25.0)
    wqi = calculate_wqi(obs)
    assert wqi == pytest.approx(0.0, abs=1e-9)


def test_wqi_calculation_known_value():
    """Sanity check WQI against a hand-computed value for non-ideal inputs."""
    obs = make_observation(ph=8.5, tds=500.0, turbidity=5.0, temperature=30.0)
    wqi = calculate_wqi(obs)
    # All parameters at their 'standard' limit -> each Qi == 100 -> WQI == 100
    assert wqi == pytest.approx(100.0, abs=1e-6)


# 2. WQI category -------------------------------------------------------------
def test_wqi_category_excellent():
    assert classify_wqi(10.0) == "Excellent"


def test_wqi_category_boundaries():
    assert classify_wqi(0.0) == "Excellent"
    assert classify_wqi(25.0) == "Good"
    assert classify_wqi(50.0) == "Poor"
    assert classify_wqi(75.0) == "Very Poor"
    assert classify_wqi(150.0) == "Unsuitable for Drinking"


def test_evaluate_observation_returns_wqi_and_category():
    obs = make_observation(ph=7.2, tds=350, turbidity=4.5, temperature=25.4)
    result = evaluate_observation(obs)
    assert "wqi" in result
    assert "quality_category" in result
    assert isinstance(result["wqi"], float)
    assert isinstance(result["quality_category"], str)


# 3. Invalid pH ----------------------------------------------------------------
def test_invalid_ph_negative_rejected():
    obs = make_observation(ph=-1.0)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


def test_invalid_ph_above_14_rejected():
    obs = make_observation(ph=14.5)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


# 4. Invalid TDS -----------------------------------------------------------------
def test_invalid_tds_negative_rejected():
    obs = make_observation(tds=-10.0)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


# 5. Invalid turbidity -------------------------------------------------------------
def test_invalid_turbidity_negative_rejected():
    obs = make_observation(turbidity=-2.0)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


# 6. Invalid temperature -------------------------------------------------------------
def test_invalid_temperature_impossible_value_rejected():
    obs = make_observation(temperature=1000.0)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


def test_invalid_temperature_below_range_rejected():
    obs = make_observation(temperature=-999.0)
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


def test_missing_parameter_rejected():
    obs = make_observation()
    del obs["ph"]
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


def test_invalid_source_rejected():
    obs = make_observation(source="live_but_fake")
    with pytest.raises(ObservationValidationError):
        validate_observation(obs)


def test_valid_observation_passes_validation():
    obs = make_observation()
    # Should not raise.
    validate_observation(obs)
