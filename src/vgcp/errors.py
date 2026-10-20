"""Exception types and small numeric helpers shared across the package."""

from __future__ import annotations

import math
from typing import Any


class ConfigError(ValueError):
    """A configuration file is missing, malformed, or violates a stated assumption."""


class InvalidActionError(ValueError):
    """A control action is not a member of the bounded action set A."""


def is_real(x: Any) -> bool:
    """True for int/float values, excluding bool (which is an int subclass)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def is_finite_real(x: Any) -> bool:
    """True for a finite int/float (not bool). Never raises: an int too large to
    convert to float counts as non-finite instead of raising OverflowError."""
    if not is_real(x):
        return False
    try:
        return math.isfinite(x)
    except OverflowError:
        return False


def json_safe(x: Any) -> Any:
    """Convert NaN/inf floats (not valid JSON) into None / "inf" / "-inf" recursively."""
    if isinstance(x, float):
        if math.isnan(x):
            return None
        if math.isinf(x):
            return "inf" if x > 0 else "-inf"
        return x
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    return x
