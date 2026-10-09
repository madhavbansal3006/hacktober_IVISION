"""
Water Quality module for the Shiggaon Watershed Intelligence System.

This package provides:
    - A simple water-quality observation schema
    - A configurable Weighted Arithmetic Water Quality Index (WQI) calculator
    - Basic validation of observation values
    - A deterministic water-quality reading simulator

See README.md for methodology, assumptions, and limitations.
"""

from .wqi import (
    PARAMETER_STANDARDS,
    ObservationValidationError,
    calculate_wqi,
    classify_wqi,
    evaluate_observation,
    validate_observation,
)
from .simulator import generate_readings

__all__ = [
    "PARAMETER_STANDARDS",
    "ObservationValidationError",
    "calculate_wqi",
    "classify_wqi",
    "evaluate_observation",
    "validate_observation",
    "generate_readings",
]
