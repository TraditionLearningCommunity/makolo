from __future__ import annotations

from html.parser import HTMLParser

from .adaptive_contracts import AdaptiveAcquisitionPolicy
from .contracts import ObservationOutcome
from .runtime_contracts import AcquisitionResult, ObservationClaim


_NON_EXECUTABLE_SCRIPT_TYPES = frozenset(
    {
        "application/ld+json",
        "application/json",
        "application/schema+json",
        "importmap",
        "speculationrules",
    }
)
_JAVASCRIPT_TYPES = frozenset(
    {
        "module",
        "text/javascript",
        "application/javascript",
        "text/ecmascript",
        "application/ecmascript",
    }
)


class _ExecutableScriptProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.executable_script = False

    def handle_starttag(self, tag, attrs) -> None:
        if self.executable_script or tag.lower() != "script":
            return
        attributes = {
            str(key).lower(): (value or "")
            for key, value in attrs
            if key
        }
        declared = attributes.get("type", "").strip().lower()
        if not declared:
            self.executable_script = True
            return
        media_type = declared.split(";", 1)[0].strip()
        if media_type in _NON_EXECUTABLE_SCRIPT_TYPES:
            return
        if (
            media_type in _JAVASCRIPT_TYPES
            or media_type.endswith("/javascript")
            or media_type.endswith("/ecmascript")
        ):
            self.executable_script = True


def _looks_like_html(result: AcquisitionResult) -> bool:
    if result.outcome is not ObservationOutcome.OBSERVED:
        return False
    if result.response_status is None or not 200 <= result.response_status < 300:
        return False
    for artifact in result.artifacts:
        if artifact.role != "http_response_body":
            continue
        media_types = {
            (artifact.declared_media_type or "").lower(),
            (artifact.detected_media_type or "").lower(),
        }
        if "text/html" in media_types or "application/xhtml+xml" in media_types:
            return True
    return False


def needs_browser_render(
    result: AcquisitionResult,
    *,
    policy: AdaptiveAcquisitionPolicy,
) -> bool:
    """Return whether technical HTML structure justifies one Browser attempt."""

    if not _looks_like_html(result):
        return False
    artifact = next(
        (
            item
            for item in result.artifacts
            if item.role == "http_response_body"
        ),
        None,
    )
    if artifact is None or not artifact.content:
        return False

    probe = _ExecutableScriptProbe()
    try:
        probe.feed(
            artifact.content[: policy.html_probe_bytes].decode(
                artifact.charset or "utf-8",
                errors="replace",
            )
        )
        probe.close()
    except (LookupError, ValueError):
        probe = _ExecutableScriptProbe()
        probe.feed(
            artifact.content[: policy.html_probe_bytes].decode(
                "utf-8",
                errors="replace",
            )
        )
        probe.close()
    return probe.executable_script


class AdaptiveObservationPlan:
    """One bounded HTTP probe followed by at most one Browser attempt."""

    def __init__(
        self,
        *,
        policy: AdaptiveAcquisitionPolicy,
        http_acquisition,
        browser_acquisition,
    ) -> None:
        self.policy = policy
        self.http_acquisition = http_acquisition
        self.browser_acquisition = browser_acquisition

    def initial_acquisition(self, claim: ObservationClaim):
        return self.http_acquisition

    def next_acquisition(
        self,
        claim: ObservationClaim,
        *,
        previous_acquisition,
        result: AcquisitionResult,
    ):
        if previous_acquisition is not self.http_acquisition:
            return None
        if needs_browser_render(result, policy=self.policy):
            return self.browser_acquisition
        return None
