"""
simulator.py
------------

A very simple, deterministic water-quality reading simulator.

IMPORTANT: Every record produced by this module has "source": "simulation".
These are NOT real Shiggaon Taluk measurements. They are plausible sample
values intended for development, testing, and demonstration only.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Plausible sample ranges for each parameter. These are only meant to
# produce realistic-looking test data, not to represent any official
# project or regulatory range.
SIMULATED_RANGES = {
    "ph": (6.5, 8.5),
    "tds": (100.0, 800.0),
    "turbidity": (0.5, 10.0),
    "temperature": (18.0, 32.0),
}

SOURCE_LABEL = "simulation"


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def generate_readings(
    mws_id: str,
    mws_code: str,
    count: int = 1,
    seed: Optional[int] = None,
    start_time: Optional[datetime] = None,
    interval_minutes: int = 60,
) -> List[Dict]:
    """
    Generate `count` simulated water-quality readings for a micro-watershed.

    Args:
        mws_id: canonical id, e.g. "g_mws.240575"
        mws_code: hydrological/display code, e.g. "4D4F2m3"
        count: number of readings to generate (>= 1)
        seed: optional random seed. Passing the same seed (and the same
              other arguments) always produces the same output.
        start_time: optional UTC datetime for the first reading.
                    Defaults to the current UTC time.
        interval_minutes: spacing between successive simulated readings.

    Returns:
        A list of observation dicts, each with:
            id, MWS, timestamp, ph, tds, turbidity, temperature, source
        where source is always "simulation".
    """
    if count < 1:
        raise ValueError("count must be >= 1")

    rng = random.Random(seed)
    base_time = start_time or datetime.now(timezone.utc)

    readings = []
    for i in range(count):
        timestamp = base_time + timedelta(minutes=interval_minutes * i)
        reading = {
            "id": mws_id,
            "MWS": mws_code,
            "timestamp": timestamp.isoformat(),
            "ph": _round(rng.uniform(*SIMULATED_RANGES["ph"])),
            "tds": _round(rng.uniform(*SIMULATED_RANGES["tds"])),
            "turbidity": _round(rng.uniform(*SIMULATED_RANGES["turbidity"])),
            "temperature": _round(rng.uniform(*SIMULATED_RANGES["temperature"])),
            "source": SOURCE_LABEL,
        }
        readings.append(reading)

    return readings
