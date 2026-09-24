"""Available-load lists the athlete confirms in the load sheet.

The athlete supplies both numbers — their known working load and the step
their own equipment moves in — so the list is a convenience for entering
equipment they already have, never an invented increment. The host still
sends the confirmed list through ``configureLoad``.
"""

from __future__ import annotations

import math

from .errors import require

STEPS_EACH_SIDE = 10
MAX_STEP = 1000.0


def load_steps(base: float, step: float) -> list[float]:
    """``base`` ± ``STEPS_EACH_SIDE`` steps, dropping negatives, rounded to remove float drift."""
    require(
        math.isfinite(base) and base >= 0 and math.isfinite(step) and 0 < step <= MAX_STEP,
        "invalid",
        "Use a nonnegative load and a positive equipment step.",
    )
    loads = [round(base + index * step, 4) for index in range(-STEPS_EACH_SIDE, STEPS_EACH_SIDE + 1)]
    return [load for load in loads if load >= 0]
