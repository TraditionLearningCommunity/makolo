from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .browser_contracts import BrowserAcquisitionPolicy
from .errors import ObserverContractError
from .http_contracts import HttpAcquisitionPolicy


def _positive_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ObserverContractError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class AdaptiveAcquisitionPolicy:
    """Versioned public HTTP→Browser escalation policy.

    Escalation is based only on technical HTML structure. It never inspects
    business meaning and never changes the external-access authority.
    """

    http_policy: HttpAcquisitionPolicy
    browser_policy: BrowserAcquisitionPolicy
    html_probe_bytes: int = 256 * 1024

    def __post_init__(self) -> None:
        if not isinstance(self.http_policy, HttpAcquisitionPolicy):
            raise ObserverContractError(
                "http_policy must be HttpAcquisitionPolicy"
            )
        if not isinstance(self.browser_policy, BrowserAcquisitionPolicy):
            raise ObserverContractError(
                "browser_policy must be BrowserAcquisitionPolicy"
            )
        if (
            self.browser_policy.http_policy.profile_fingerprint
            != self.http_policy.profile_fingerprint
            or self.browser_policy.http_policy.policy_fingerprint
            != self.http_policy.policy_fingerprint
        ):
            raise ObserverContractError(
                "adaptive HTTP and Browser policies must share one HTTP policy"
            )
        object.__setattr__(
            self,
            "html_probe_bytes",
            _positive_int("html_probe_bytes", self.html_probe_bytes),
        )

    @property
    def profile_key(self) -> str:
        return "public-adaptive"

    @property
    def profile_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "mode": "public-adaptive",
            "http_profile_fingerprint": self.http_policy.profile_fingerprint,
            "browser_profile_fingerprint": (
                self.browser_policy.profile_fingerprint
            ),
            "html_probe_bytes": self.html_probe_bytes,
            "escalation_signal": "executable_script_v1",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "public-adaptive:v1:" + hashlib.sha256(encoded).hexdigest()

    @property
    def policy_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "profile_fingerprint": self.profile_fingerprint,
            "http_policy_fingerprint": self.http_policy.policy_fingerprint,
            "browser_policy_fingerprint": (
                self.browser_policy.policy_fingerprint
            ),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "observer-adaptive:v1:" + hashlib.sha256(encoded).hexdigest()
