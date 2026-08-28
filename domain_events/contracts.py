"""Stable application contracts for Makolo domain facts."""


class DomainEventType:
    ACTIVITY_PUBLISHED = "activity.published"
    ACTIVITY_REOPENED = "activity.reopened"
    OCCURRENCE_RESCHEDULED = "occurrence.rescheduled"
    OCCURRENCE_CANCELLED = "occurrence.cancelled"
    OCCURRENCE_REOPENED = "occurrence.reopened"

    JOURNEY_SUBMITTED = "journey.submitted"
    JOURNEY_PENDING_APPROVAL = "journey.pending_approval"
    JOURNEY_APPROVED = "journey.approved"
    JOURNEY_REJECTED = "journey.rejected"
    JOURNEY_PENDING_PAYMENT = "journey.pending_payment"
    JOURNEY_CONFIRMED = "journey.confirmed"
    JOURNEY_IN_PROGRESS = "journey.in_progress"
    JOURNEY_FULFILLED = "journey.fulfilled"
    JOURNEY_CANCELLED = "journey.cancelled"
    JOURNEY_EXPIRED = "journey.expired"

    JOURNEY_STEP_READY = "journey.step.ready"
    JOURNEY_STEP_STARTED = "journey.step.started"
    JOURNEY_STEP_COMPLETED = "journey.step.completed"
    JOURNEY_STEP_BLOCKED = "journey.step.blocked"
    JOURNEY_BLOCKER_CREATED = "journey.blocker.created"
    JOURNEY_BLOCKER_RESOLVED = "journey.blocker.resolved"
    JOURNEY_ASSIGNMENT_CREATED = "journey.assignment.created"
    JOURNEY_ASSIGNMENT_ENDED = "journey.assignment.ended"
    JOURNEY_ARTIFACT_CREATED = "journey.artifact.created"
    JOURNEY_ARTIFACT_REVIEW_REQUESTED = "journey.artifact.review_requested"
    JOURNEY_ARTIFACT_REVIEW_COMPLETED = "journey.artifact.review_completed"

    OPPORTUNITY_REVISION_PUBLISHED = "opportunity.revision.published"
    OPPORTUNITY_SOURCE_CHANGED = "opportunity.source.changed"
    OPPORTUNITY_WITHDRAWN = "opportunity.withdrawn"
    OPPORTUNITY_MERGED = "opportunity.merged"
    SERVICE_OPPORTUNITY_REVISION_ADOPTED = "service.opportunity_revision.adopted"

    REQUEST_CREATED = "request.created"
    REQUEST_APPROVED = "request.approved"
    REQUEST_REJECTED = "request.rejected"

    COMMERCE_ORDER_CREATED = "commerce.order.created"
    COMMERCE_ORDER_CONFIRMED = "commerce.order.confirmed"
    COMMERCE_ORDER_CANCELLED = "commerce.order.cancelled"
    COMMERCE_ORDER_EXPIRED = "commerce.order.expired"

    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    ACCESS_ISSUED = "access.issued"
    ACCESS_USED = "access.used"
    ACCESS_REVOKED = "access.revoked"
    ACCESS_EXPIRED = "access.expired"
    ACCESS_TRANSFERRED = "access.transferred"

    values = frozenset(value for name, value in vars().items() if name.isupper() and isinstance(value, str))


JOURNEY_STATUS_EVENT_TYPES = {
    "submitted": DomainEventType.JOURNEY_SUBMITTED,
    "pending_approval": DomainEventType.JOURNEY_PENDING_APPROVAL,
    "approved": DomainEventType.JOURNEY_APPROVED,
    "rejected": DomainEventType.JOURNEY_REJECTED,
    "pending_payment": DomainEventType.JOURNEY_PENDING_PAYMENT,
    "confirmed": DomainEventType.JOURNEY_CONFIRMED,
    "in_progress": DomainEventType.JOURNEY_IN_PROGRESS,
    "fulfilled": DomainEventType.JOURNEY_FULFILLED,
    "cancelled": DomainEventType.JOURNEY_CANCELLED,
    "expired": DomainEventType.JOURNEY_EXPIRED,
}
