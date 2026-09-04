from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .proactive_preparation import reevaluate_for_domain_event


CONSUMER_NAME = "preparation.proactive"
EVENT_TYPES = {
    DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
    DomainEventType.OPPORTUNITY_WITHDRAWN,
    DomainEventType.JOURNEY_SUBMITTED,
    DomainEventType.JOURNEY_PENDING_APPROVAL,
    DomainEventType.JOURNEY_APPROVED,
    DomainEventType.JOURNEY_REJECTED,
    DomainEventType.JOURNEY_PENDING_PAYMENT,
    DomainEventType.JOURNEY_CONFIRMED,
    DomainEventType.JOURNEY_IN_PROGRESS,
    DomainEventType.JOURNEY_FULFILLED,
    DomainEventType.JOURNEY_CANCELLED,
    DomainEventType.JOURNEY_EXPIRED,
    DomainEventType.JOURNEY_STEP_READY,
    DomainEventType.JOURNEY_STEP_STARTED,
    DomainEventType.JOURNEY_STEP_COMPLETED,
    DomainEventType.JOURNEY_STEP_BLOCKED,
    DomainEventType.JOURNEY_BLOCKER_CREATED,
    DomainEventType.JOURNEY_BLOCKER_RESOLVED,
    DomainEventType.FORM_REQUESTED,
    DomainEventType.FORM_SUBMITTED,
    DomainEventType.FORM_REOPENED,
    DomainEventType.PAYMENT_OBLIGATION_CREATED,
    DomainEventType.PAYMENT_OBLIGATION_PROCESSING,
    DomainEventType.PAYMENT_OBLIGATION_SATISFIED,
    DomainEventType.PAYMENT_OBLIGATION_WAIVED,
    DomainEventType.PAYMENT_OBLIGATION_EXPIRED,
    DomainEventType.PAYMENT_OBLIGATION_CANCELLED,
    DomainEventType.PAYMENT_OBLIGATION_REFUNDED,
    DomainEventType.PAYMENT_SUCCEEDED,
    DomainEventType.PAYMENT_FAILED,
    DomainEventType.PAYMENT_REFUNDED,
    DomainEventType.ACCESS_ISSUED,
    DomainEventType.ACCESS_USED,
    DomainEventType.ACCESS_REVOKED,
    DomainEventType.ACCESS_EXPIRED,
    DomainEventType.ACCESS_TRANSFERRED,
    DomainEventType.OCCURRENCE_RESCHEDULED,
    DomainEventType.OCCURRENCE_CANCELLED,
    DomainEventType.OCCURRENCE_REOPENED,
}


register_consumer(CONSUMER_NAME, reevaluate_for_domain_event, event_types=EVENT_TYPES)
