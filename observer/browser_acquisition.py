from __future__ import annotations

from datetime import timedelta
from email.message import Message

from .browser_contracts import (
    BrowserAcquisitionPolicy,
    BrowserRenderFailure,
)
from .contracts import (
    ArtifactCompleteness,
    ArtifactOrigin,
    AttemptStrategy,
    ObservationOutcome,
)
from .http_contracts import HttpResourceFailure
from .ports import BrowserRendererPort
from .runtime_contracts import (
    AcquiredArtifact,
    AcquisitionResult,
    ObservationClaim,
)


_RETRYABLE_MAIN_STATUSES = frozenset(
    {408, 425, 429, 500, 502, 503, 504}
)


def _content_type(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    message = Message()
    message["content-type"] = value
    return (
        message.get_content_type().lower() or None,
        message.get_content_charset() or None,
    )


class BrowserRenderAcquisition:
    """Public JavaScript rendering with no browser-owned external network."""

    strategy = AttemptStrategy.BROWSER_RENDER

    def __init__(
        self,
        *,
        policy: BrowserAcquisitionPolicy,
        http_acquisition,
        renderer: BrowserRendererPort,
        clock,
    ) -> None:
        self.policy = policy
        self.http_acquisition = http_acquisition
        self.renderer = renderer
        self.clock = clock

    def _failure(
        self,
        *,
        code: str,
        observed_at,
        retry_at=None,
        response_status=None,
        final_locator=None,
        wire_bytes=0,
        decoded_bytes=0,
        redirect_count=0,
    ) -> AcquisitionResult:
        return AcquisitionResult(
            outcome=ObservationOutcome.FAILED,
            observed_at=observed_at,
            final_locator=final_locator,
            response_status=response_status,
            failure_code=code,
            retry_at=retry_at,
            wire_bytes=wire_bytes,
            decoded_bytes=decoded_bytes,
            redirect_count=redirect_count,
        )

    def acquire(self, claim: ObservationClaim) -> AcquisitionResult:
        started_at = self.clock()
        if claim.kind != "web_url":
            return self._failure(
                code="browser.unsupported_target_kind",
                observed_at=started_at,
            )

        deadline_at = min(
            started_at + timedelta(
                seconds=self.policy.http_policy.max_observation_seconds
            ),
            claim.leased_until,
        )
        session = self.http_acquisition.open_resource_session(
            deadline_at=deadline_at
        )

        def load_resource(request):
            remaining_wire = (
                self.policy.max_total_wire_bytes
                - session.stats.wire_bytes
            )
            remaining_decoded = (
                self.policy.max_total_decoded_bytes
                - session.stats.decoded_bytes
            )
            if remaining_wire <= 0:
                raise HttpResourceFailure(
                    "browser.total_wire_budget_exceeded"
                )
            if remaining_decoded <= 0:
                raise HttpResourceFailure(
                    "browser.total_decoded_budget_exceeded"
                )
            result = session.fetch(
                request.url,
                headers=dict(request.headers),
                max_wire_bytes=min(
                    self.policy.http_policy.max_wire_bytes,
                    remaining_wire,
                ),
                max_decoded_bytes=min(
                    self.policy.http_policy.max_decoded_bytes,
                    remaining_decoded,
                ),
            )
            if session.stats.wire_bytes > self.policy.max_total_wire_bytes:
                raise HttpResourceFailure(
                    "browser.total_wire_budget_exceeded"
                )
            if (
                session.stats.decoded_bytes
                > self.policy.max_total_decoded_bytes
            ):
                raise HttpResourceFailure(
                    "browser.total_decoded_budget_exceeded"
                )
            return result

        try:
            rendered = self.renderer.render(
                start_url=claim.locator,
                policy=self.policy,
                resource_loader=load_resource,
                deadline_at=deadline_at,
                clock=self.clock,
            )
        except BrowserRenderFailure as exc:
            observed_at = self.clock()
            retry_at = exc.retry_at
            if exc.retryable and retry_at is None:
                retry_at = observed_at + timedelta(
                    seconds=self.policy.http_policy.retry_seconds
                )
            return self._failure(
                code=exc.code,
                observed_at=observed_at,
                retry_at=retry_at,
                response_status=exc.response_status,
                wire_bytes=session.stats.wire_bytes,
                decoded_bytes=session.stats.decoded_bytes,
            )
        except HttpResourceFailure as exc:
            observed_at = self.clock()
            return self._failure(
                code=exc.code,
                observed_at=observed_at,
                retry_at=exc.retry_at,
                response_status=exc.response_status,
                wire_bytes=session.stats.wire_bytes,
                decoded_bytes=session.stats.decoded_bytes,
            )
        finally:
            session.close()

        observed_at = self.clock()
        if rendered.response_status in _RETRYABLE_MAIN_STATUSES:
            retry_at = rendered.retry_at or (
                observed_at
                + timedelta(seconds=self.policy.http_policy.retry_seconds)
            )
            return self._failure(
                code=(
                    "http.rate_limited"
                    if rendered.response_status == 429
                    else "http.server_error"
                    if rendered.response_status >= 500
                    else "http.retryable_status"
                ),
                observed_at=observed_at,
                retry_at=retry_at,
                response_status=rendered.response_status,
                final_locator=rendered.final_locator,
                wire_bytes=session.stats.wire_bytes,
                decoded_bytes=session.stats.decoded_bytes,
                redirect_count=(
                    session.stats.redirect_count
                    + rendered.redirect_count
                ),
            )

        artifacts = []
        media_type, charset = _content_type(
            rendered.main_response_headers.get("content-type")
        )
        if rendered.main_response_body:
            artifacts.append(
                AcquiredArtifact(
                    content=rendered.main_response_body,
                    role="browser_main_response_body",
                    captured_at=observed_at,
                    origin=ArtifactOrigin.CAPTURED,
                    completeness=ArtifactCompleteness.COMPLETE,
                    declared_media_type=media_type,
                    charset=charset,
                )
            )

        dom = rendered.rendered_dom
        dom_completeness = (
            ArtifactCompleteness.INCOMPLETE
            if rendered.incomplete
            else ArtifactCompleteness.COMPLETE
        )
        if len(dom) > self.policy.max_rendered_dom_bytes:
            dom = dom[: self.policy.max_rendered_dom_bytes]
            dom_completeness = ArtifactCompleteness.TRUNCATED
        artifacts.append(
            AcquiredArtifact(
                content=dom,
                role="rendered_dom",
                captured_at=observed_at,
                origin=ArtifactOrigin.RENDERED,
                completeness=dom_completeness,
                declared_media_type="text/html",
                detected_media_type="text/html",
                charset=(
                    "utf-8"
                    if dom_completeness
                    is not ArtifactCompleteness.TRUNCATED
                    else None
                ),
            )
        )

        return AcquisitionResult(
            outcome=ObservationOutcome.OBSERVED,
            observed_at=observed_at,
            final_locator=rendered.final_locator,
            response_status=rendered.response_status,
            artifacts=tuple(artifacts),
            redirect_count=(
                    session.stats.redirect_count
                    + rendered.redirect_count
                ),
            wire_bytes=session.stats.wire_bytes,
            decoded_bytes=session.stats.decoded_bytes,
        )
