"""
wqi.py
------

Implements the Weighted Arithmetic Water Quality Index (WQI) for the
Shiggaon Watershed Intelligence System's water-quality module.

METHOD
======
This module implements the generic "Weighted Arithmetic Water Quality
Index" method that is commonly used in watershed and surface-water quality
studies (sometimes attributed to Horton/Brown-style weighted-arithmetic
formulations). This formula itself is NOT defined by BIS 10500 or any
single regulatory standard -- BIS 10500 (and similar references) are only
used here as a *source of plausible reference/standard values* for each
parameter, because the exact project-specific constants for Shiggaon
Taluk were not supplied.

For each parameter i:

    Qi = |Vi - Vo_i| / (Si - Vo_i) * 100

        Vi   = observed value of parameter i
        Vo_i = "ideal" value of parameter i (0 for most pollutants,
               7.0 for pH, and an assumed ambient value for temperature)
        Si   = "standard" / permissible reference value of parameter i

    Wi = K / Si
    K  = 1 / sum(1 / Si for all parameters)

    WQI = sum(Wi * Qi) / sum(Wi)

ASSUMPTIONS (see README.md for full discussion)
================================================
The exact Shiggaon project WQI constants were not provided. The values
below are reasonable, commonly-referenced defaults and are clearly labeled
as ASSUMPTIONS, not official project or BIS values. They are grouped in a
single dictionary (PARAMETER_STANDARDS) so they can be replaced with
project-approved constants in one place, without touching any calculation
logic.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# CONFIGURABLE CONSTANTS -- edit these to match official project values.
# ---------------------------------------------------------------------------
#
# ideal   -> Vo_i, the "perfect water" value for the parameter
# standard-> Si, the permissible/reference limit used to normalize the
#            parameter into a 0-100 "quality rating" scale
#
# pH, TDS, and Turbidity reference values below are commonly cited
# desirable/permissible limits seen in Indian drinking-water quality
# literature (of which BIS 10500 is one well-known source). They are
# ASSUMED defaults for this module, not confirmed Shiggaon project
# constants.
#
# Temperature has no universal regulatory "quality limit" the way pH/TDS/
# turbidity do. The ideal/standard pair below is an ASSUMED local ambient
# baseline (25 C) with an assumed acceptable deviation band (+/-5 C),
# included only so temperature can be expressed on the same 0-100 scale.
# This is the weakest-justified parameter in the index and should be
# reviewed by the project team before production use.
PARAMETER_STANDARDS: Dict[str, Dict[str, float]] = {
    "ph": {"ideal": 7.0, "standard": 8.5},
    "tds": {"ideal": 0.0, "standard": 500.0},
    "turbidity": {"ideal": 0.0, "standard": 5.0},
    "temperature": {"ideal": 25.0, "standard": 30.0},
}

# Hard validity bounds (physically/plausibly impossible values are rejected
# regardless of the WQI reference values above).
VALID_RANGES: Dict[str, Tuple[float, float]] = {
    "ph": (0.0, 14.0),
    "tds": (0.0, float("inf")),
    "turbidity": (0.0, float("inf")),
    # Generous but finite bounds for ambient/water temperature in Celsius.
    "temperature": (-5.0, 60.0),
}

# Quality categories for the final WQI score. Boundaries follow the
# commonly used weighted-arithmetic WQI category scheme (see README.md).
QUALITY_CATEGORIES: Tuple[Tuple[float, float, str], ...] = (
    (0.0, 25.0, "Excellent"),
    (25.0, 50.0, "Good"),
    (50.0, 75.0, "Poor"),
    (75.0, 100.0, "Very Poor"),
    (100.0, float("inf"), "Unsuitable for Drinking"),
)

REQUIRED_PARAMETERS = ("ph", "tds", "turbidity", "temperature")
SUPPORTED_SOURCES = ("simulation", "historical", "live")


class ObservationValidationError(ValueError):
    """Raised when a water-quality observation contains invalid values."""


def validate_observation(observation: Dict) -> None:
    """
    Validate a water-quality observation dict.

    Checks:
        - all required parameters are present
        - pH is within [0, 14]
        - TDS is non-negative
        - turbidity is non-negative
        - temperature is within a plausible physical range
        - 'source' (if present) is one of SUPPORTED_SOURCES

    Raises:
        ObservationValidationError if any check fails.
    """
    missing = [p for p in REQUIRED_PARAMETERS if p not in observation]
    if missing:
        raise ObservationValidationError(
            f"Missing required parameter(s): {', '.join(missing)}"
        )

    for param in REQUIRED_PARAMETERS:
        value = observation[param]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ObservationValidationError(
                f"Parameter '{param}' must be numeric, got {type(value).__name__}"
            )
        low, high = VALID_RANGES[param]
        if value < low or value > high:
            raise ObservationValidationError(
                f"Parameter '{param}' value {value} is outside the valid "
                f"range [{low}, {high}]"
            )

    source = observation.get("source")
    if source is not None and source not in SUPPORTED_SOURCES:
        raise ObservationValidationError(
            f"Unsupported source '{source}'. Must be one of {SUPPORTED_SOURCES}"
        )


def _quality_rating(param: str, value: float) -> float:
    """Compute Qi for a single parameter."""
    ideal = PARAMETER_STANDARDS[param]["ideal"]
    standard = PARAMETER_STANDARDS[param]["standard"]
    denom = standard - ideal
    if denom == 0:
        raise ValueError(f"Invalid standard/ideal configuration for '{param}'")
    return abs(value - ideal) / denom * 100.0


def _weight(param: str, k: float) -> float:
    """Compute Wi for a single parameter."""
    return k / PARAMETER_STANDARDS[param]["standard"]


def calculate_wqi(observation: Dict) -> float:
    """
    Calculate the Weighted Arithmetic WQI for a validated observation.

    The observation must contain 'ph', 'tds', 'turbidity', and
    'temperature'. Call validate_observation() first if the values have
    not already been checked.

    Returns:
        float: the WQI score (0 = ideal, higher = worse).
    """
    k = 1.0 / sum(1.0 / PARAMETER_STANDARDS[p]["standard"] for p in REQUIRED_PARAMETERS)

    weighted_sum = 0.0
    weight_total = 0.0
    for param in REQUIRED_PARAMETERS:
        qi = _quality_rating(param, observation[param])
        wi = _weight(param, k)
        weighted_sum += wi * qi
        weight_total += wi

    return weighted_sum / weight_total


def classify_wqi(wqi: float) -> str:
    """Map a numeric WQI score to a quality category label."""
    for low, high, label in QUALITY_CATEGORIES:
        if low <= wqi < high:
            return label
    # Fallback for the open-ended top bracket (handles wqi == inf edge case)
    return QUALITY_CATEGORIES[-1][2]


@dataclass
class WQIResult:
    wqi: float
    quality_category: str

    def as_dict(self) -> Dict:
        return {"wqi": round(self.wqi, 2), "quality_category": self.quality_category}


def evaluate_observation(observation: Dict, validate: bool = True) -> Dict:
    """
    Validate (optionally) and score a single observation.

    Returns the derived output:
        {"wqi": <float>, "quality_category": <str>}
    """
    if validate:
        validate_observation(observation)
    wqi = calculate_wqi(observation)
    category = classify_wqi(wqi)
    return WQIResult(wqi=wqi, quality_category=category).as_dict()
