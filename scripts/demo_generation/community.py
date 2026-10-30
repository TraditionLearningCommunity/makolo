"""Synthetic scenarios for Group, Dossier/Project, in-app Notification and Trust.

Only pre-existing world_* profiles and demo- Activities are eligible. Never
send real email/push and never invent a verified Proof or external outcome.
"""
import argparse
from collections import Counter


DOMAINS = {"groups", "objectives", "notifications", "trust", "contributions"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default=",".join(sorted(DOMAINS)))
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= DOMAINS:
        p.error("Domains: groups,objectives,notifications,trust,contributions")
    if not 1 <= a.count <= 2000 or not 2 <= a.profiles <= 100:
        p.error("count 1..2000 and profiles 2..100 required")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from groups.models import Group, GroupMembership
    from groups.services import create_group, add_member
    from objectives.models import Dossier, Project, DossierJourneyLink, ProjectDossierLink
    from objectives.services import (create_dossier, create_project, link_journey,
                                     link_dossier_to_project)
    from journeys.models import Journey
    from notifications.models import Notification, NotificationCategory, NotificationKind
    from notifications.services import create_notification
    from trust.models import Feedback
    from trust.services import can_submit_feedback, submit_feedback
    from social.models import Contribution, ContributionKind
    from social.services import create_contribution
    if connection.vendor != "sqlite":
        p.error("SQLite demo database required")
    users = list(get_user_model().objects.filter(
        username__startswith="world_", is_active=True, is_staff=False,
        is_superuser=False).order_by("username")[:a.profiles])
    if len(users) < 2:
        p.error("Two active world_* profiles required")

    counts = Counter()
    if "groups" in selected:
        for index, owner in enumerate(users[:min(a.count, len(users))]):
            name = "[DEMO] Groupe d'entraide " + owner.username
            group = Group.objects.filter(owner_profile=owner, name=name).first()
            if group is None:
                if not a.apply:
                    counts["groups_planned"] += 1
                    continue
                try:
                    with transaction.atomic():
                        group = create_group(actor=owner, name=name,
                            description="Groupe fictif pour tester la participation.")
                    counts["groups_created"] += 1
                except (ValidationError, PermissionDenied):
                    counts["groups_rejected"] += 1
                    continue
            else:
                counts["groups_existing"] += 1
            member = users[(index + 1) % len(users)]
            if GroupMembership.objects.filter(group=group, profile=member,
                                              status="active").exists():
                counts["members_existing"] += 1
            elif not a.apply:
                counts["members_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        add_member(actor=owner, group=group, profile=member)
                    counts["members_added"] += 1
                except (ValidationError, PermissionDenied):
                    counts["members_rejected"] += 1

    if "objectives" in selected:
        for owner in users[:min(a.count, len(users))]:
            title = "[DEMO] Preparer une demarche - " + owner.username
            long_title = "[DEMO] Projet d'action - " + owner.username
            dossier = Dossier.objects.filter(owner_profile=owner, title=title).first()
            project = Project.objects.filter(owner_profile=owner, title=long_title).first()
            if not a.apply:
                counts["dossiers_planned"] += int(dossier is None)
                counts["projects_planned"] += int(project is None)
                continue
            try:
                with transaction.atomic():
                    if project is None:
                        project = create_project(actor=owner, owner_profile=owner,
                            title=long_title, description="Horizon fictif de tests Makolo.")
                        counts["projects_created"] += 1
                    if dossier is None:
                        dossier = create_dossier(actor=owner, owner_profile=owner,
                            title=title, description="Objectif fictif relie aux Journeys.")
                        counts["dossiers_created"] += 1
                    if not ProjectDossierLink.objects.filter(
                        project=project, dossier=dossier, is_active=True).exists():
                        link_dossier_to_project(actor=owner, project=project, dossier=dossier)
                        counts["project_links_created"] += 1
                    journey = Journey.objects.filter(beneficiary=owner,
                        activity__slug__startswith="demo-").order_by("-created_at").first()
                    if journey and not DossierJourneyLink.objects.filter(
                        dossier=dossier, journey=journey, is_active=True).exists():
                        link_journey(actor=owner, dossier=dossier, journey=journey)
                        counts["journey_links_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["objectives_rejected"] += 1

    if "notifications" in selected:
        rows = Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-"
        ).select_related("beneficiary", "activity").order_by("id")[:a.count]
        for journey in rows:
            key = "demo-generation:journey:" + str(journey.pk)
            if Notification.objects.filter(dedup_key=key).exists():
                counts["notifications_existing"] += 1
            elif not a.apply:
                counts["notifications_planned"] += 1
            else:
                with transaction.atomic():
                    create_notification(
                        recipient=journey.beneficiary,
                        kind=NotificationKind.SYSTEM,
                        category=NotificationCategory.SERVICE,
                        title="Demarche de demonstration",
                        message="Scenario fictif lie a votre demarche Makolo.",
                        dedup_key=key, activity=journey.activity, journey=journey,
                        metadata={"synthetic_demo": True},
                        queue_email=False, queue_push=False)
                counts["notifications_created"] += 1

    if "trust" in selected:
        rows = Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-"
        ).select_related("beneficiary", "activity", "occurrence").order_by("id")[:a.count * 20]
        eligible = 0
        for journey in rows:
            if eligible >= a.count:
                break
            if Feedback.objects.filter(journey=journey, author=journey.beneficiary).exists():
                counts["feedback_existing"] += 1
                continue
            if not can_submit_feedback(journey=journey, actor=journey.beneficiary):
                counts["feedback_not_yet_eligible"] += 1
                continue
            eligible += 1
            if not a.apply:
                counts["feedback_planned"] += 1
                continue
            try:
                with transaction.atomic():
                    submit_feedback(
                        journey=journey, actor=journey.beneficiary,
                        overall_sentiment="neutral",
                        comment="Retour fictif, genere pour les tests Makolo.")
                counts["feedback_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["feedback_rejected"] += 1

    if "contributions" in selected:
        rows = Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-"
        ).select_related("beneficiary", "activity").order_by("id")[:a.count * 5]
        seen = set()
        for journey in rows:
            key = (journey.activity_id, journey.beneficiary_id)
            if key in seen or len(seen) >= a.count:
                continue
            seen.add(key)
            message = "[DEMO] Conseil contextuel : verifier les informations de cette activite avant d'agir."
            if Contribution.objects.filter(
                activity=journey.activity, author_profile=journey.beneficiary,
                body=message, kind=ContributionKind.TIP
            ).exists():
                counts["contributions_existing"] += 1
            elif not a.apply:
                counts["contributions_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        create_contribution(actor=journey.beneficiary,
                            kind=ContributionKind.TIP, activity=journey.activity,
                            body=message)
                    counts["contributions_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["contributions_rejected"] += 1

    print("COMMUNITY", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))
    print("No external delivery, fake verification, forced Membership authority or fabricated Proof.")


if __name__ == "__main__":
    main()
