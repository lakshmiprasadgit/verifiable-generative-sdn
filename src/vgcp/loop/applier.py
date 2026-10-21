"""The single enforcement point between decisions and the network (audit M3).

A certificate is only evidence; it protects nothing unless the code that changes the
network checks it. CertifiedApplier is the only shielded path to
NetworkBackend.apply() and refuses an action unless

  1. the certificate accepted exactly this action (Certificate.authorizes), and
  2. the certificate was issued for the observation the loop is acting on (state
     and demand fingerprints match), and
  3. the certificate is not older than max_age_s on the controller clock.

The one exception is the fallback pi_0, which paper Remark 1 deploys when no
candidate is certified. It is applied without a certificate, but only if it is
exactly the configured pi_0, and the record says whether pi_0 itself was certified
(if not, Assumption 3 failed in that state).

UncheckedApplier exists only for the unshielded baseline and says so in its name.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vgcp.action import ControlAction, action_fingerprint
from vgcp.loop.interfaces import ControllerFailure, NetworkBackend, Observation
from vgcp.shield import Certificate, observation_fingerprint


class UnauthorizedActionError(RuntimeError):
    """An action reached the applier without a valid certificate."""


@dataclass(frozen=True)
class ApplyRecord:
    action: ControlAction
    kind: str  # "certified" | "fallback" | "unchecked"
    applied: bool  # False if the backend rejected it (ControllerFailure)
    detail: str = ""


class CertifiedApplier:
    def __init__(self, backend: NetworkBackend, fallback: ControlAction, max_age_s: float) -> None:
        if not (math.isfinite(max_age_s) and max_age_s >= 0):
            raise ValueError("max_age_s must be a finite number >= 0")
        self._backend = backend
        self._fallback_fp = action_fingerprint(fallback)
        self.max_age_s = max_age_s

    def apply_certified(self, action: ControlAction, cert: Certificate, obs: Observation) -> ApplyRecord:
        if not cert.authorizes(action):
            raise UnauthorizedActionError("certificate does not authorize this action")
        if (cert.state_fingerprint != observation_fingerprint(obs.state)
                or cert.demand_fingerprint != observation_fingerprint(obs.demand)):
            raise UnauthorizedActionError("certificate was issued for a different observation")
        if cert.now_s is None or not (0 <= obs.now_s - cert.now_s <= self.max_age_s):
            raise UnauthorizedActionError(
                f"certificate age {None if cert.now_s is None else obs.now_s - cert.now_s} s "
                f"outside [0, {self.max_age_s}] s"
            )
        return self._apply(action, "certified")

    def apply_fallback(self, action: ControlAction, reason: str) -> ApplyRecord:
        if action_fingerprint(action) != self._fallback_fp:
            raise UnauthorizedActionError("only the configured fallback pi_0 may be applied without a certificate")
        return self._apply(action, "fallback", reason)

    def _apply(self, action: ControlAction, kind: str, detail: str = "") -> ApplyRecord:
        try:
            self._backend.apply(action)
        except ControllerFailure as exc:
            return ApplyRecord(action, kind, False, f"controller failure: {exc}")
        return ApplyRecord(action, kind, True, detail)


class UncheckedApplier:
    """Baseline only: applies whatever it is given, with no certificate."""

    def __init__(self, backend: NetworkBackend) -> None:
        self._backend = backend

    def apply_unchecked(self, action: ControlAction) -> ApplyRecord:
        try:
            self._backend.apply(action)
        except ControllerFailure as exc:
            return ApplyRecord(action, "unchecked", False, f"controller failure: {exc}")
        return ApplyRecord(action, "unchecked", True)
