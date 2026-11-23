"""Synthetic scenarios for Group, Dossier/Project, in-app Notification and Trust.

Only pre-existing world_* profiles and demo- Activities are eligible. Never
send real email/push and never invent a verified Proof or external outcome.
"""
import argparse
from collections import Counter


DOMAINS = {"groups", "objectives", "notifications", "trust", "contributions", "sharing"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default=",".join(sorted(DOMAINS)))
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--profile-username")
    p.add_argument("--objectives-projects", type=int, default=4)
    p.add_argument("--objectives-dossiers-per-project", type=int, default=3)
    p.add_argument("--objectives-independent", type=int, default=2)
    p.add_argument("--objectives-journeys-per-dossier", type=int, default=2)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= DOMAINS:
        p.error("Domains: groups,objectives,notifications,trust,contributions,sharing")
    if not 1 <= a.count <= 2000 or not 1 <= a.profiles <= 100:
        p.error("count 1..2000 and profiles 2..100 required")
    if not (1 <= a.objectives_projects <= 8
            and 1 <= a.objectives_dossiers_per_project <= 6
            and 0 <= a.objectives_independent <= 6
            and 0 <= a.objectives_journeys_per_dossier <= 4):
        p.error("Objectives: projects 1..8, dossiers-per-project 1..6, independent 0..6, journeys-per-dossier 0..4")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from groups.models import Group, GroupMembership
    from groups.services import create_group, add_member
    from journeys.models import Journey
    from notifications.models import Notification, NotificationCategory, NotificationKind
    from notifications.services import create_notification
    from trust.models import Feedback, Proof, ProofType, Report, ReportCategory
    from trust.services import can_submit_feedback, submit_feedback, issue_proof, create_report
    from social.models import Contribution, ContributionKind
    from social.services import create_contribution
    from sharing.models import ActivityShareSubject, ShareIntent
    from sharing.services import create_activity_share
    if connection.vendor != "sqlite":
        p.error("SQLite demo database required")
    from .schema import DemoSchemaNotReady, assert_demo_schema_ready
    try:
        assert_demo_schema_ready()
    except DemoSchemaNotReady as exc:
        p.error(str(exc))
    from .selection import demo_profiles
    from .editorial import group_name
    from .objectives import generate as generate_objectives
    users = demo_profiles(username=a.profile_username, limit=a.profiles)


    counts = Counter()
    if "groups" in selected:
        for index, owner in enumerate(users[:min(a.count, len(users))]):
            name = group_name(owner)
            group = (Group.objects.filter(owner_profile=owner, name=name).first()
                     or Group.objects.filter(owner_profile=owner, name="[DEMO] Groupe d'entraide " + owner.username).first()
                     or Group.objects.filter(owner_profile=owner, name="Groupe d'entraide " + owner.username).first())
            if group is None:
                if not a.apply:
                    counts["groups_planned"] += 1
                    continue
                try:
                    with transaction.atomic():
                        group = create_group(actor=owner, name=name,
                            description="Échanger des informations utiles, préparer des actions et s’entraider dans les démarches.")
                    counts["groups_created"] += 1
                except (ValidationError, PermissionDenied):
                    counts["groups_rejected"] += 1
                    continue
            else:
                counts["groups_existing"] += 1
            member = users[(index + 1) % len(users)] if len(users) > 1 else None
            if member is None:
                counts["members_skipped_single_profile"] += 1
            elif GroupMembership.objects.filter(group=group, profile=member,
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
        counts.update(generate_objectives(
            users,
            count=a.count,
            projects_per_profile=a.objectives_projects,
            dossiers_per_project=a.objectives_dossiers_per_project,
            independent_dossiers=a.objectives_independent,
            journeys_per_dossier=a.objectives_journeys_per_dossier,
            apply=a.apply,
        ))

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
                        title="Suivi de votre démarche",
                        message="Retrouvez les étapes et les informations utiles pour « " + journey.activity.title[:140] + " ».",
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
                        comment="Les étapes étaient compréhensibles, mais quelques précisions pratiques seraient utiles pour la suite.")
                counts["feedback_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["feedback_rejected"] += 1

    if "trust" in selected:
        # Proof is produced ONLY from canonical AccessUse accepted / Journey
        # completion, never from raw seed flags or synthetic verification.
        verified = (Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-",
            accesses__uses__result="accepted"
        ).select_related("beneficiary").distinct().order_by("id")[:a.count])
        for journey in verified:
            if Proof.objects.filter(journey=journey,
                proof_type=ProofType.ACCESS_USED).exists():
                counts["proofs_existing"] += 1
            elif not a.apply:
                counts["proofs_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        issue_proof(journey=journey,
                            proof_type=ProofType.ACCESS_USED,
                            actor=None, is_public=False)
                    counts["proofs_issued"] += 1
                except (ValidationError, PermissionDenied):
                    counts["proofs_not_eligible"] += 1
        # Small fraction of journeys produce synthetic incident reports
        # for the moderation flow; the reports never imply actual harm.
        reported = (Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-"
        ).select_related("beneficiary").order_by("id")[:a.count])
        for index, journey in enumerate(reported):
            if index % 5:
                continue
            description = "Le point d’accueil était difficile à repérer à mon arrivée."
            if Report.objects.filter(journey=journey,
                reporter=journey.beneficiary, description__in=(description, "[DEMO] Signalement fictif : accueil difficile a localiser.", "Signalement fictif : accueil difficile a localiser.")).exists():
                counts["reports_existing"] += 1
            elif not a.apply:
                counts["reports_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        create_report(actor=journey.beneficiary,
                            category=ReportCategory.ACCESS_PROBLEM,
                            description=description, journey=journey)
                    counts["reports_created"] += 1
                except (ValidationError, PermissionDenied):
                    counts["reports_rejected"] += 1

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
            message = "Avant de vous déplacer, vérifiez les horaires et les conditions publiés pour « " + journey.activity.title[:140] + " »."
            if Contribution.objects.filter(
                activity=journey.activity, author_profile=journey.beneficiary,
                body__in=(message, "[DEMO] Conseil contextuel : verifier les informations de cette activite avant d'agir.", "Conseil contextuel : verifier les informations de cette activite avant d'agir."), kind=ContributionKind.TIP
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

    if "sharing" in selected:
        rows = Journey.objects.filter(
            beneficiary__in=users, activity__slug__startswith="demo-",
            activity__status="published", activity__visibility="public"
        ).select_related("beneficiary", "activity").order_by("id")[:a.count * 8]
        seen = set()
        for journey in rows:
            if len(seen) >= a.count:
                break
            key = (journey.activity_id, journey.beneficiary_id)
            if key in seen:
                continue
            seen.add(key)
            if ActivityShareSubject.objects.filter(
                activity=journey.activity,
                envelope__created_by=journey.beneficiary,
                envelope__intent=ShareIntent.VIEW,
            ).exists():
                counts["shares_existing"] += 1
            elif not a.apply:
                counts["shares_planned"] += 1
            else:
                try:
                    with transaction.atomic():
                        # Token is deliberately not printed, logged or exported.
                        create_activity_share(created_by=journey.beneficiary,
                            activity=journey.activity, intent=ShareIntent.VIEW)
                    counts["shares_created"] += 1
                except (PermissionDenied, ValidationError):
                    counts["shares_rejected"] += 1

    print("COMMUNITY", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))
    print(
        "PERIMETRE: seuls les domaines demandes ci-dessus ont ete traites. "
        "Les comptes indiquent les objets effectivement crees ou reutilises. "
        "Aucun envoi externe ; les Access et credentials internes sont generes "
        "par le domaine access lorsqu'il est selectionne."
    )


if __name__ == "__main__":
    main()
