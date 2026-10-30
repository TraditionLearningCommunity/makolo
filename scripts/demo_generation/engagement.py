"""Reconcile synthetic CRM contacts and attach basic Forms to demo Journeys.

Forms use canonical authoring/request services and are not substituted for
Requirement or Proof. CRM contacts are derived from existing demo sales facts.
"""
import argparse
from collections import Counter


DOMAINS = {"forms", "crm"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default="forms,crm")
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= DOMAINS:
        p.error("Domains: forms,crm")
    if not 1 <= a.count <= 2000:
        p.error("count 1..2000 required")
    import django
    django.setup()
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from activities.models import Activity, ActivityStatus
    from authorization.constants import PermissionCode
    from authorization.services import can
    from journeys.models import Journey
    from tickets.models import TicketOrder, Ticket
    from crm.services import sync_contact_from_order, sync_contact_from_ticket
    from questionnaires.models import Form, FormVersion, FormRequest, QuestionType
    from questionnaires.services import (
        create_form, create_form_version, add_question,
        publish_form_version, request_form,
    )
    if connection.vendor != "sqlite":
        p.error("SQLite demo database required")
    counts = Counter()

    if "crm" in selected:
        orders = TicketOrder.objects.filter(
            event__activity__slug__startswith="demo-",
            buyer__username__startswith="world_",
        ).select_related("event", "event__activity", "buyer").order_by("id")[:a.count]
        for order in orders:
            if not getattr(order.event, "organization", None):
                counts["crm_no_organization"] += 1
                continue
            if not a.apply:
                counts["crm_orders_planned"] += 1
                continue
            with transaction.atomic():
                if sync_contact_from_order(order) is not None:
                    counts["crm_orders_reconciled"] += 1
        tickets = Ticket.objects.filter(
            event__activity__slug__startswith="demo-",
            owner__username__startswith="world_",
        ).select_related("event", "event__activity", "owner").order_by("id")[:a.count]
        for ticket in tickets:
            if not getattr(ticket.event, "organization", None):
                counts["crm_no_organization"] += 1
                continue
            if not a.apply:
                counts["crm_tickets_planned"] += 1
                continue
            with transaction.atomic():
                if sync_contact_from_ticket(ticket) is not None:
                    counts["crm_tickets_reconciled"] += 1

    if "forms" in selected:
        activities = Activity.objects.filter(
            slug__startswith="demo-", status=ActivityStatus.PUBLISHED,
        ).select_related("owner_profile", "created_by").order_by("id")[:a.count * 8]
        attempted = 0
        for activity in activities:
            if attempted >= a.count:
                break
            actor = activity.owner_profile or activity.created_by
            if actor is None or not actor.is_active or not can(
                actor, PermissionCode.ACTIVITY_MANAGE, activity=activity
            ):
                counts["forms_no_authority"] += 1
                continue
            journey = Journey.objects.filter(activity=activity,
                beneficiary__username__startswith="world_").order_by("id").first()
            if not journey:
                counts["forms_no_journey"] += 1
                continue
            attempted += 1
            key = "demo-preparation"
            form = Form.objects.filter(activity=activity, key=key).first()
            version = (FormVersion.objects.filter(form=form, status="published")
                       .order_by("-version").first()) if form else None
            existing = (FormRequest.objects.filter(form_version=version,journey=journey)
                        .exists()) if version else False
            if existing:
                counts["form_requests_existing"] += 1
                continue
            if not a.apply:
                counts["form_requests_planned"] += 1
                continue
            try:
                with transaction.atomic():
                    if form is None:
                        form = create_form(activity=activity, key=key,
                            title="Preparation de demonstration", actor=actor)
                        counts["forms_created"] += 1
                    if version is None:
                        version = create_form_version(form=form, actor=actor)
                        add_question(form_version=version, actor=actor,
                            key="notes", label="Informations utiles pour votre demarche",
                            question_type=QuestionType.LONG_TEXT,
                            position=1, required=False)
                        publish_form_version(form_version=version, actor=actor)
                        counts["form_versions_created"] += 1
                    if not FormRequest.objects.filter(
                        form_version=version, journey=journey
                    ).exists():
                        request_form(form_version=version, journey=journey,
                                     actor=actor, required=False)
                        counts["form_requests_created"] += 1
            except (PermissionDenied, ValidationError):
                counts["forms_rejected"] += 1

    print("ENGAGEMENT", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))
    print("CRM is derived from existing facts; Forms are not Requirements or Proof.")


if __name__ == "__main__":
    main()
