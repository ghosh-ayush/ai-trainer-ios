"""Nutrient validation and portion scaling. Estimates are the athlete's, never inferred."""

from __future__ import annotations

import math
from typing import Any

from .errors import DomainError

JSON = dict[str, Any]

NUTRIENT_KEYS = ("calories", "protein", "carbs", "fat")


def _is_amount(value: object) -> bool:
    """A finite, non-negative int or float. ``bool`` is deliberately excluded."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value >= 0


def _is_positive_amount(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0


def validate_nutrients(nutrients: JSON) -> None:
    if not all(_is_amount(nutrients[key]) for key in NUTRIENT_KEYS):
        raise DomainError("invalid", "Nutrient estimates must be finite and nonnegative.")


def scale_nutrients(nutrients: JSON, servings: object = 1) -> JSON:
    """Multiply every nutrient by ``servings``; reject non-positive or overflowing results."""
    validate_nutrients(nutrients)
    if not _is_positive_amount(servings):
        raise DomainError("invalid", "Servings must be greater than zero.")
    factor = float(servings) if isinstance(servings, float) else servings
    scaled: JSON = {key: value * factor for key, value in nutrients.items()}
    if not all(math.isfinite(value) for value in scaled.values()):
        raise DomainError("invalid", "Nutrient estimates must be finite and nonnegative.")
    return scaled
