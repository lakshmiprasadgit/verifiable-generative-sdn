"""Discrete-time signal traces for STL evaluation.

A Trace holds, for each signal name, one sample per control slot k = 0..N-1,
where slot k corresponds to time t0 + k*Delta_t. Samples are floats; a missing
or invalid measurement is stored as NaN. Infinite sample values are treated as
invalid measurements and also stored as NaN (recorded in ``invalid``).
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from vgcp.errors import is_finite_real, is_real


class UnknownSignalError(KeyError):
    """A formula references a signal the trace does not define."""


class Trace:
    def __init__(self, samples: Mapping[str, Sequence[float | None]], length: int | None = None):
        lengths = {len(v) for v in samples.values()}
        if length is not None:
            lengths.add(length)
        if len(lengths) != 1:
            raise ValueError(f"all signals must have the same length, got {sorted(lengths)}")
        self.length: int = lengths.pop()
        if self.length < 1:
            raise ValueError("a trace needs at least one sample")
        self.invalid: set[tuple[str, int]] = set()
        self._data: dict[str, tuple[float, ...]] = {}
        for name, seq in samples.items():
            out = []
            for k, v in enumerate(seq):
                if v is None:
                    out.append(math.nan)
                elif not is_real(v):
                    raise TypeError(f"signal {name}[{k}]: not a number ({v!r})")
                elif not is_finite_real(v) and not (isinstance(v, float) and math.isnan(v)):
                    # +/-inf, or an int too large for a float
                    self.invalid.add((name, k))
                    out.append(math.nan)
                else:
                    out.append(float(v))
            self._data[name] = tuple(out)

    @classmethod
    def from_steps(cls, steps: Sequence[Mapping[str, float | None]]) -> "Trace":
        """Build from per-step valuations; a name absent at some step is missing (NaN) there."""
        names = sorted({n for step in steps for n in step})
        return cls({n: [step.get(n) for step in steps] for n in names}, length=len(steps))

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._data)

    def value(self, name: str, k: int) -> float:
        if name not in self._data:
            raise UnknownSignalError(name)
        if not 0 <= k < self.length:
            raise IndexError(f"sample {k} outside trace of length {self.length}")
        return self._data[name][k]
