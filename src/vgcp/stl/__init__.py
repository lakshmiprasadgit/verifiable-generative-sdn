"""Signal Temporal Logic: syntax (paper Eq 7) and robustness (paper Eqs 8-11)."""

from vgcp.stl.ast import (
    Always,
    And,
    Eventually,
    Formula,
    Not,
    Or,
    Predicate,
    Top,
    Until,
    false,
    max_temporal_bound,
    required_horizon,
    signal_offsets,
    signals,
    to_text,
)
from vgcp.stl.parser import ParseError, parse
from vgcp.stl.robustness import (
    StlResult,
    TraceTooShortError,
    Verdict,
    evaluate,
    robustness,
    satisfied,
)
from vgcp.stl.signal import Trace, UnknownSignalError

__all__ = [
    "Always", "And", "Eventually", "Formula", "Not", "Or", "Predicate", "Top", "Until",
    "false", "max_temporal_bound", "required_horizon", "signal_offsets", "signals", "to_text",
    "ParseError", "parse",
    "StlResult", "TraceTooShortError", "Verdict", "evaluate", "robustness", "satisfied",
    "Trace", "UnknownSignalError",
]
