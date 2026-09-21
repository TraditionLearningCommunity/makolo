from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from journeys.models import RequestStatus
from readiness import ReadinessCheckState
from services.requirement_services import derive_requirement_consequence

from core.product_language import vocabulary_for


def _iso(value):
    return value.isoformat() if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _time(value):
    return value.isoformat() if value is not None else None


def _api_url(value):
    if not value:
        return None
    value = str(value)
    return value if value.startswith("/api/") else None


def _vocabulary_payload(vocabulary):
    return {
        "vertical": vocabulary.vertical,
        "activity_noun": vocabulary.activity_noun,
        "occurrence_noun": vocabulary.occurrence_noun,
        "journey_noun": vocabulary.journey_noun,
        "request_noun": vocabulary.request_noun,
        "access_noun": vocabulary.access_noun,
    }


def _readiness_check(check):
    payload = {
        "key": check.key,
        "source": check.source,
        "state": check.state.value,
        "reason": check.reason_code,
        "summary": check.summary,
    }
    if check.next_action is not None:
        payload["next"] = {
            "key": check.next_action.key,
            "label": check.next_action.label,
            "link": _api_url(check.next_action.url),
        }
    return payload


def serialize_readiness(readiness):
    ready = []
    actor_interventions = []
    waiting = []
    blockers = []
    for check in readiness.checks:
        payload = _readiness_check(check)
        if check.state == ReadinessCheckState.SATISFIED:
            ready.append(payload)
        elif check.state == ReadinessCheckState.ACTION_REQUIRED:
            actor_interventions.append(payload)
        elif check.state == ReadinessCheckState.WAITING:
            waiting.append(payload)
        elif check.state == ReadinessCheckState.BLOCKING:
            blockers.append(payload)

    next_action = None
    if readiness.next_action is not None:
        next_action = {
            "key": readiness.next_action.key,
            "label": readiness.next_action.label,
            "source": readiness.next_action.source,
            "link": _api_url(readiness.next_action.url),
        }
    return {
        "state": readiness.status.value,
        "observed_at": readiness.observed_at.isoformat(),
        "ready": ready,
        "actor_interventions": actor_interventions,
        "waiting": waiting,
        "blockers": blockers,
        "next": next_action,
    }


def _request_payload(request):
    return {
        "id": str(request.pk),
        "purpose": request.purpose,
        "state": request.status,
        "submitted_at": _iso(request.submitted_at),
        "expires_at": _iso(request.expires_at),
    }


def _occurrence_ref(occurrence):
    if occurrence is None:
        return None
    return {
        "kind": "occurrence",
        "id": str(occurrence.pk),
        "label": occurrence.label or None,
        "state": occurrence.status,
        "timing": {
            "kind": occurrence.timing_kind,
            "start_date": _date(occurrence.start_date),
            "start_time": _time(occurrence.start_time),
            "end_date": _date(occurrence.end_date),
            "end_time": _time(occurrence.end_time),
            "start_at": _iso(occurrence.start_at),
            "end_at": _iso(occurrence.end_at),
            "timezone": occurrence.timezone,
        },
    }


def _payment_payload(payment):
    if payment is None:
        return None
    return {
        "id": str(payment.pk),
        "state": payment.status,
        "amount": str(payment.amount),
        "currency": payment.currency,
    }


def _payment_summary(journey, profile):
    orders = list(journey.commerce_orders.all())
    obligations = list(journey.payment_obligations.all())
    if not orders and not obligations:
        return None

    order = (
        sorted(
            orders,
            key=lambda row: (row.created_at, str(row.pk)),
            reverse=True,
        )[0]
        if orders
        else None
    )
    order_payments = list(order.payments.all()) if order is not None else []
    order_payment = (
        sorted(
            order_payments,
            key=lambda row: (row.created_at, str(row.pk)),
            reverse=True,
        )[0]
        if order_payments
        else None
    )

    obligation_rows = []
    for obligation in obligations:
        payments = list(obligation.payments.all())
        payment = (
            sorted(
                payments,
                key=lambda row: (row.created_at, str(row.pk)),
                reverse=True,
            )[0]
            if payments
            else None
        )
        row = {
            "id": str(obligation.pk),
            "state": obligation.status,
            "reason": obligation.reason,
            "amount": str(obligation.amount),
            "currency": obligation.currency,
            "processing_mode": obligation.processing_mode,
            "due_at": _iso(obligation.due_at),
            "payment": _payment_payload(payment),
            "links": {},
        }
        if payment is not None:
            row["links"]["payment"] = (
                f"/api/v1/payments/payments/{payment.pk}/"
            )
        obligation_rows.append(row)

    links = {}
    if order_payment is not None:
        links["payment"] = (
            f"/api/v1/payments/payments/{order_payment.pk}/"
        )

    return {
        "order": (
            {
                "id": str(order.pk),
                "state": order.status,
                "payment_mode": order.payment_mode,
                "total": str(order.total),
                "currency": order.currency,
                "expires_at": _iso(order.expires_at),
            }
            if order is not None
            else None
        ),
        "payment": _payment_payload(order_payment),
        "obligations": obligation_rows,
        "links": links,
    }


def _access_summary(journey, profile):
    accesses = [row for row in journey.accesses.all() if row.beneficiary_id == profile.pk]
    if not accesses:
        return None
    access = sorted(accesses, key=lambda row: (row.created_at, str(row.pk)), reverse=True)[0]
    return {
        "id": str(access.pk),
        "state": access.status,
        "valid_from": _iso(access.valid_from),
        "valid_until": _iso(access.valid_until),
        "link": f"/api/v1/me/accesses/{access.pk}/",
    }


def _service_requirements(journey):
    try:
        context = journey.service_context
    except ObjectDoesNotExist:
        return []
    except AttributeError:
        return []

    rows = context.requirement_assessments.select_related("requirement").prefetch_related(
        "payment_obligation_links__obligation",
        "step_links__journey_step",
        "evidence",
    ).order_by("requirement__position", "created_at", "id")
    payload = []
    for assessment in rows:
        consequence = derive_requirement_consequence(assessment)
        requirement = assessment.requirement
        payload.append(
            {
                "id": str(assessment.pk),
                "requirement_id": str(requirement.pk),
                "label": requirement.title,
                "kind": requirement.kind,
                "required": bool(requirement.is_mandatory),
                "state": assessment.status,
                "consequence": consequence.value if consequence is not None else None,
                "link": f"/api/v1/me/journeys/{journey.pk}/requirements/{assessment.pk}/",
            }
        )
    return payload


def build_journey_detail(*, journey, readiness, profile, live=None):
    vocabulary = vocabulary_for(activity=journey.activity, workflow=journey.workflow)
    pending = [
        _request_payload(row)
        for row in journey.requests.all()
        if row.status == RequestStatus.PENDING
    ]
    rejected = [
        _request_payload(row)
        for row in journey.requests.all()
        if row.status == RequestStatus.REJECTED
    ]
    capabilities = []
    links = {
        "self": f"/api/v1/me/journeys/{journey.pk}/",
        "resources": f"/api/v1/preparation/journeys/{journey.pk}/resources/",
        "activity": f"/api/v1/activities/{journey.activity_id}/",
    }
    if journey.occurrence_id:
        links["occurrence"] = f"/api/v1/occurrences/{journey.occurrence_id}/"
    if live is not None:
        links["live"] = f"/api/v1/operations/occurrences/{journey.occurrence_id}/live/"
        capabilities.append("open_live")

    form_links = [
        {
            "id": str(row.pk),
            "required": bool(row.required),
            "state": row.status,
            "due_at": _iso(row.due_at),
            "link": f"/api/v1/questionnaires/requests/{row.pk}/",
        }
        for row in journey.form_requests.all()
    ]

    return {
        "identity": {
            "kind": "journey",
            "id": str(journey.pk),
            "workflow": journey.workflow,
        },
        "representation": {
            "title": journey.activity.title,
            "kind_label": vocabulary.journey_noun,
            "summary": journey.activity.short_description or None,
            "vocabulary": _vocabulary_payload(vocabulary),
        },
        "state": {
            "code": journey.status,
            "label": journey.get_status_display(),
        },
        "readiness": serialize_readiness(readiness),
        "requests": {"pending": pending, "rejected": rejected},
        "requirements": _service_requirements(journey),
        "forms": form_links,
        "activity": {
            "kind": "activity",
            "id": str(journey.activity_id),
            "title": journey.activity.title,
        },
        "occurrence": _occurrence_ref(journey.occurrence),
        "payment": _payment_summary(journey, profile),
        "access": _access_summary(journey, profile),
        "resources": {
            "state": "available",
            "link": f"/api/v1/preparation/journeys/{journey.pk}/resources/",
        },
        "capabilities": capabilities,
        "links": links,
    }


def build_requirement_detail(*, journey, assessment):
    requirement = assessment.requirement
    consequence = derive_requirement_consequence(assessment)
    ways = []
    links = {
        "journey": f"/api/v1/me/journeys/{journey.pk}/",
    }

    payment_links = list(assessment.payment_obligation_links.select_related("obligation").all())
    if payment_links:
        ways.append(
            {
                "kind": "payment",
                "state": payment_links[0].obligation.status,
            }
        )

    step_links = list(assessment.step_links.select_related("journey_step").all())
    for link in step_links:
        ways.append(
            {
                "kind": "journey_step",
                "id": str(link.journey_step_id),
                "state": link.journey_step.status,
                "label": link.journey_step.title,
            }
        )

    return {
        "identity": {
            "kind": "requirement_assessment",
            "id": str(assessment.pk),
            "requirement_id": str(requirement.pk),
            "journey_id": str(journey.pk),
        },
        "requirement": {
            "kind": requirement.kind,
            "label": requirement.title,
            "description": requirement.description or None,
            "required": bool(requirement.is_mandatory),
        },
        "assessment": {
            "state": assessment.status,
            "consequence": consequence.value if consequence is not None else None,
            "reason": None,
        },
        "ways_to_satisfy": ways,
        "capabilities": [],
        "links": links,
    }


def build_access_detail(*, access, profile):
    beneficiary = access.beneficiary_id == profile.pk
    relationship = "beneficiary" if beneficiary else "purchased_for_other"

    journey_ref = None
    if access.journey_id and beneficiary and access.journey.beneficiary_id == profile.pk:
        journey_ref = {
            "kind": "journey",
            "id": str(access.journey_id),
            "link": f"/api/v1/me/journeys/{access.journey_id}/",
        }

    occurrence = None
    if access.occurrence_id:
        occurrence = {
            "kind": "occurrence",
            "id": str(access.occurrence_id),
            "link": f"/api/v1/occurrences/{access.occurrence_id}/",
        }

    return {
        "identity": {"kind": "access", "id": str(access.pk)},
        "right": {
            "state": access.status,
            "single_use": bool(access.single_use),
            "valid_from": _iso(access.valid_from),
            "valid_until": _iso(access.valid_until),
        },
        "holder": {"relationship": relationship},
        "activity": {
            "kind": "activity",
            "id": str(access.activity_id),
            "title": access.activity.title,
            "link": f"/api/v1/activities/{access.activity_id}/",
        },
        "occurrence": occurrence,
        "journey": journey_ref,
        "capabilities": [],
        "links": {
            "self": f"/api/v1/me/accesses/{access.pk}/",
        },
    }
