"""Control action a_t and the bounded action set A (paper Eq 2).

Stage 1 action components (a subset of those listed in paper Sec 2.1):

* ``path[slice]``             routing choice among configured paths   (discrete)
* ``rate_budget_mbps[slice]`` slice resource budget                   (continuous)
* ``admission_limit[slice]``  admission-control threshold, devices    (integer)
* ``link_power[link]``        link power state for controllable links (binary)

Not modelled in Stage 1: P4 table entries, O-RAN RIC parameters and queue
scheduling weights (no corresponding data-plane element in the prototype yet).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from vgcp.errors import InvalidActionError, is_real

_FIELDS = ("path", "rate_budget_mbps", "admission_limit", "link_power")


@dataclass(frozen=True)
class SliceSpec:
    name: str
    allowed_paths: tuple[str, ...]
    rate_budget_mbps: tuple[float, float]
    admission_limit: tuple[int, int]


@dataclass(frozen=True)
class ControlAction:
    path: Mapping[str, str]
    rate_budget_mbps: Mapping[str, float]
    admission_limit: Mapping[str, int]
    link_power: Mapping[str, bool]

    def __post_init__(self) -> None:
        # Copy each mapping into a read-only view so that an action cannot change after
        # it has been verified, neither in place nor through the caller's original dict.
        # Non-mappings are left as they are for ActionSchema.validate to reject.
        for f in _FIELDS:
            value = getattr(self, f)
            if isinstance(value, Mapping):
                object.__setattr__(self, f, MappingProxyType(dict(value)))

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {f: dict(getattr(self, f)) for f in _FIELDS}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControlAction":
        if not isinstance(data, Mapping):
            raise InvalidActionError("action must be a mapping")
        if set(data) != set(_FIELDS):
            raise InvalidActionError(f"action must have exactly the fields {list(_FIELDS)}")
        for f in _FIELDS:
            if not isinstance(data[f], Mapping):
                raise InvalidActionError(f"action field '{f}' must be a mapping")
        return cls(**{f: dict(data[f]) for f in _FIELDS})


def action_fingerprint(action: Any) -> str | None:
    """SHA-256 of a canonical form of ``action``, or None if it has no canonical form.

    Canonical form: sorted keys; path ids as strings; budgets as finite floats (so
    100 and 100.0 are the same action); admission limits as ints (not bool); power
    states as bools. Anything else - a non-action, wrong types, non-finite numbers -
    has no fingerprint, so it cannot match a certificate. Never raises.
    """
    try:
        if not isinstance(action, ControlAction):
            return None
        canon: dict[str, dict[str, Any]] = {}
        for f, ok, conv in (
            ("path", lambda v: isinstance(v, str), str),
            ("rate_budget_mbps", lambda v: is_real(v) and math.isfinite(v), float),
            ("admission_limit", lambda v: isinstance(v, int) and not isinstance(v, bool), int),
            ("link_power", lambda v: isinstance(v, bool), bool),
        ):
            items = getattr(action, f)
            if not isinstance(items, Mapping) or not all(isinstance(k, str) and ok(v) for k, v in items.items()):
                return None
            canon[f] = {k: conv(v) for k, v in items.items()}
        blob = json.dumps(canon, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(blob.encode()).hexdigest()
    except Exception:
        return None


class ActionSchema:
    """Membership test for A plus a fixed-order vector embedding (for learned policies)."""

    def __init__(
        self, slices: Sequence[SliceSpec], path_ids: Sequence[str], power_links: Sequence[str]
    ) -> None:
        self.slices: dict[str, SliceSpec] = {s.name: s for s in slices}
        self.slice_names: tuple[str, ...] = tuple(self.slices)
        self.path_ids: tuple[str, ...] = tuple(path_ids)
        self.power_links: tuple[str, ...] = tuple(power_links)

    def validate(self, action: Any) -> list[str]:
        """Reasons why ``action`` is not in A; an empty list means it is."""
        if not isinstance(action, ControlAction):
            return [f"not a ControlAction: {type(action).__name__}"]
        errors: list[str] = []
        expected_keys = {
            "path": set(self.slice_names),
            "rate_budget_mbps": set(self.slice_names),
            "admission_limit": set(self.slice_names),
            "link_power": set(self.power_links),
        }
        for f, expected in expected_keys.items():
            value = getattr(action, f)
            if not isinstance(value, Mapping):
                errors.append(f"{f}: must be a mapping")
                continue
            missing, extra = expected - set(value), set(value) - expected
            if missing:
                errors.append(f"{f}: missing entries {sorted(missing)}")
            if extra:
                errors.append(f"{f}: unexpected entries {sorted(map(str, extra))}")
        if errors:
            return errors

        for name, spec in self.slices.items():
            path = action.path[name]
            if not isinstance(path, str) or path not in self.path_ids:
                errors.append(f"path.{name}: unknown path {path!r}")
            elif path not in spec.allowed_paths:
                errors.append(f"path.{name}: path {path!r} not allowed for this slice")

            budget = action.rate_budget_mbps[name]
            lo, hi = spec.rate_budget_mbps
            if not is_real(budget) or not math.isfinite(budget):
                errors.append(f"rate_budget_mbps.{name}: not a finite number ({budget!r})")
            elif not lo <= budget <= hi:
                errors.append(f"rate_budget_mbps.{name}: {budget} outside [{lo}, {hi}]")

            limit = action.admission_limit[name]
            lo_i, hi_i = spec.admission_limit
            if not isinstance(limit, int) or isinstance(limit, bool):
                errors.append(f"admission_limit.{name}: not an integer ({limit!r})")
            elif not lo_i <= limit <= hi_i:
                errors.append(f"admission_limit.{name}: {limit} outside [{lo_i}, {hi_i}]")

        for link in self.power_links:
            if not isinstance(action.link_power[link], bool):
                errors.append(f"link_power.{link}: not a boolean ({action.link_power[link]!r})")
        return errors

    def is_valid(self, action: Any) -> bool:
        return not self.validate(action)

    def component_names(self) -> tuple[str, ...]:
        names = []
        for s in self.slice_names:
            names += [f"path.{s}", f"rate_budget_mbps.{s}", f"admission_limit.{s}"]
        names += [f"link_power.{link}" for link in self.power_links]
        return tuple(names)

    def vector_bounds(self) -> list[tuple[float, float]]:
        bounds: list[tuple[float, float]] = []
        for s in self.slices.values():
            bounds += [
                (0.0, float(len(self.path_ids) - 1)),
                (float(s.rate_budget_mbps[0]), float(s.rate_budget_mbps[1])),
                (float(s.admission_limit[0]), float(s.admission_limit[1])),
            ]
        bounds += [(0.0, 1.0)] * len(self.power_links)
        return bounds

    def to_vector(self, action: ControlAction) -> list[float]:
        """Embedding in R^{n_a}: path index, budget, limit per slice; then 0/1 per power link."""
        errors = self.validate(action)
        if errors:
            raise InvalidActionError("; ".join(errors))
        vec: list[float] = []
        for s in self.slice_names:
            vec += [
                float(self.path_ids.index(action.path[s])),
                float(action.rate_budget_mbps[s]),
                float(action.admission_limit[s]),
            ]
        vec += [1.0 if action.link_power[link] else 0.0 for link in self.power_links]
        return vec

    def from_vector(self, vec: Sequence[float]) -> ControlAction:
        """Decode a vector; raises InvalidActionError unless the result is in A.

        Discrete components must be exactly integral - no rounding is applied,
        so a malformed generator output is rejected rather than silently repaired.
        """
        n = 3 * len(self.slice_names) + len(self.power_links)
        if len(vec) != n:
            raise InvalidActionError(f"expected {n} components, got {len(vec)}")
        if not all(is_real(v) and math.isfinite(v) for v in vec):
            raise InvalidActionError("vector has non-finite or non-numeric components")

        def integral(v: float, what: str) -> int:
            if float(v) != math.floor(v):
                raise InvalidActionError(f"{what}: {v} is not an integer")
            return int(v)

        path, budget, limit = {}, {}, {}
        for i, s in enumerate(self.slice_names):
            p, b, a = vec[3 * i : 3 * i + 3]
            idx = integral(p, f"path.{s}")
            if not 0 <= idx < len(self.path_ids):
                raise InvalidActionError(f"path.{s}: index {idx} out of range")
            path[s] = self.path_ids[idx]
            budget[s] = float(b)
            limit[s] = integral(a, f"admission_limit.{s}")
        power = {}
        for j, link in enumerate(self.power_links):
            v = integral(vec[3 * len(self.slice_names) + j], f"link_power.{link}")
            if v not in (0, 1):
                raise InvalidActionError(f"link_power.{link}: {v} is not 0 or 1")
            power[link] = bool(v)
        action = ControlAction(path, budget, limit, power)
        errors = self.validate(action)
        if errors:
            raise InvalidActionError("; ".join(errors))
        return action
