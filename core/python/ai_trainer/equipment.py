"""Available-load lists the athlete confirms in the load sheet.

The athlete supplies both numbers — their known working load and the step
their own equipment moves in — so the list is a convenience for entering
equipment they already have, never an invented increment. The host still
sends the confirmed list through ``configureLoad``.
"""

from __future__ import annotations

import math
from typing import Any

from .errors import require

JSON = dict[str, Any]

STEPS_EACH_SIDE = 10
MAX_STEP = 1000.0
PLATE_TOLERANCE = 1e-6


def load_steps(base: float, step: float) -> list[float]:
    """``base`` ± ``STEPS_EACH_SIDE`` steps, dropping negatives, rounded to remove float drift."""
    require(
        math.isfinite(base) and base >= 0 and math.isfinite(step) and 0 < step <= MAX_STEP,
        "invalid",
        "Use a nonnegative load and a positive equipment step.",
    )
    loads = [round(base + index * step, 4) for index in range(-STEPS_EACH_SIDE, STEPS_EACH_SIDE + 1)]
    return [load for load in loads if load >= 0]


def plate_load(load: float, bar: float, plates: list[float]) -> JSON:
    """The plates for each side of a barbell loaded to ``load`` (ADR-021), largest first.

    ``bar`` and ``plates`` are the athlete's own equipment; pairs of each plate are assumed
    unlimited. When ``load`` cannot be made exactly, the plates for the nearest lower total are
    returned with ``exact`` false, never a heavier bar than asked for.
    """
    require(
        math.isfinite(load) and load >= 0 and math.isfinite(bar) and 0 <= bar <= MAX_STEP,
        "invalid",
        "Use a nonnegative load and bar weight.",
    )
    require(
        bool(plates) and all(math.isfinite(plate) and 0 < plate <= MAX_STEP for plate in plates),
        "invalid",
        "List at least one plate weight.",
    )
    remaining = (load - bar) / 2
    per_side: list[float] = []
    for plate in sorted(set(plates), reverse=True):
        while remaining >= plate - PLATE_TOLERANCE:
            per_side.append(plate)
            remaining -= plate
    total = round(bar + 2 * sum(per_side), 4)
    return {"perSide": per_side, "total": total, "exact": abs(total - load) < PLATE_TOLERANCE}
