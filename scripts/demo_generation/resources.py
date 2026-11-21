"""Fill the three 'Mes ressources' demo surfaces through canonical services.

Documents are private PersonalAsset versions with actual bytes; avatar content is
copied only from the selected profile itself. A generated text fixture is used
when the profile has no reusable local image. Proofs and Credentials are issued
only from existing eligible Journey/Access facts by their respective services.

Plan by default; --apply writes to the configured demo SQLite directly.
"""
import argparse
from collections import Counter

KINDS = ("documents", "proofs", "credentials")
DOCUMENT_TITLES = (
    "Fiche de préparation personnelle",
    "Notes pour mes démarches",
    "Informations de participation",
    "Récapitulatif de mes activités",
)


def demo_text(username, slot):
    """Original sample material without personal attributes or false claims."""
    return (
        "Makolo - Document de demonstration\n"
        f"Profil de test : @{username}\n"
        f"Exemple : {DOCUMENT_TITLES[slot % len(DOCUMENT_TITLES)]}\n\n"
        "Ce document fictif permet de tester la bibliotheque, le telechargement "
        "et la reutilisation dans une demarche.\n"
        "Il ne constitue ni une piece d'identite, ni une preuve, ni un certificat.\n"
    ).encode("utf-8")


def avatar_upload(user):
    """Read only the target user's own avatar, with its real bytes and MIME."""
    import mimetypes
    from django.core.files.uploadedfile import SimpleUploadedFile
    image = getattr(user, "avatar", None)
    if not image or not image.name:
        return None
    mime = mimetypes.guess_type(image.name)[0]
    if mime not in ("image/jpeg", "image/png"):
        return None
    try:
        if not image.storage.exists(image.name):
            return None
        max_bytes = 10 * 1024 * 1024
        with image.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if not data or len(data) > max_bytes:
            return None
        return SimpleUploadedFile("profile-avatar" + (
            ".png" if mime == "image/png" else ".jpg"
        ), data, content_type=mime)
    except (OSError, IOError, ValueError):
        return None


def document_slots(user, *, include_avatar):
    from django.core.files.uploadedfile import SimpleUploadedFile
    if include_avatar:
        image = avatar_upload(user)
        if image is not None:
            yield "Copie de ma photo de profil", image
    for index, title in enumerate(DOCUMENT_TITLES):
        yield title, SimpleUploadedFile(
            f"makolo-demo-resource-{index + 1}.txt", demo_text(user.username, index),
            content_type="text/plain",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", default="all",
                        help="all or documents,proofs,credentials")
    parser.add_argument("--count", type=int, default=4,
                        help="Maximum new items per domain and selected profile")
    parser.add_argument("--profiles", type=int, default=30)
    parser.add_argument("--profile-username", help="Existing target profile username")
    parser.add_argument("--include-test-users", action="store_true",
                        help="Include existing synthetic beta_* and mobile_mature_* accounts")
    parser.add_argument("--reuse-avatar", action="store_true", default=True,
                        help="Use the selected user's own avatar if available (default)")
    parser.add_argument("--no-reuse-avatar", dest="reuse_avatar", action="store_false",
                        help="Use generated demo text documents only")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    domains = set(KINDS) if args.domains == "all" else set(args.domains.split(","))
    if not domains or not domains <= set(KINDS):
        parser.error("Expected domains: documents,proofs,credentials or all")
    if not 1 <= args.count <= 30 or not 1 <= args.profiles <= 100:
        parser.error("--count 1..30, --profiles 1..100")
    if args.profile_username and not args.profile_username.strip():
        parser.error("--profile-username cannot be empty")

    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError, PermissionDenied
    from django.db import connection, transaction
    from django.db.models import Q
    from personal_assets.models import PersonalAsset
    from personal_assets.services import create_personal_asset, create_personal_asset_version
    from journeys.collaboration_models import JourneyArtifactKind
    from journeys.models import Journey, JourneyStatus
    from access.models import AccessUseResult
    from trust.models import Proof, ProofType
    from trust.services import issue_proof
    from trust.credential_models import Credential, CredentialType
    from trust.credential_services import issue_credential
    from .scope import backup_demo_sqlite

    if connection.vendor != "sqlite":
        parser.error("Resources generator operates on the configured demo SQLite only")
    users_qs = get_user_model().objects.filter(
        is_active=True, is_staff=False, is_superuser=False
    )
    if args.profile_username:
        users_qs = users_qs.filter(username=args.profile_username)
    elif args.include_test_users:
        users_qs = users_qs.filter(
            Q(username__startswith="world_")
            | Q(username__startswith="beta_")
            | Q(username__startswith="mobile_mature_")
        )
    else:
        users_qs = users_qs.filter(username__startswith="world_")
    users = list(users_qs.order_by("username")[:args.profiles])
    if not users:
        parser.error("No eligible existing profile for the requested selector")
    # A named account is never silently included in broad seeding.
    if args.backup and args.apply:
        print("BACKUP", backup_demo_sqlite(connection))

    counters = Counter()
    for user in users:
        if "documents" in domains:
            existing = set(PersonalAsset.objects.filter(
                controller=user, subject_profile=user, archived_at__isnull=True,
            ).values_list("title", flat=True))
            created = 0
            for title, upload in document_slots(user, include_avatar=args.reuse_avatar):
                if created >= args.count:
                    break
                if title in existing:
                    counters["documents_existing"] += 1
                    continue
                created += 1
                counters["documents_planned"] += 1
                if not args.apply:
                    continue
                try:
                    with transaction.atomic():
                        asset = create_personal_asset(
                            controller=user, subject_profile=user, title=title,
                            kind=JourneyArtifactKind.OTHER,
                        )
                        create_personal_asset_version(
                            actor=user, asset=asset, uploaded_file=upload,
                        )
                    counters["documents_created"] += 1
                except (ValidationError, PermissionDenied, OSError):
                    counters["documents_rejected"] += 1

        if "proofs" in domains or "credentials" in domains:
            journeys = list(Journey.objects.filter(
                beneficiary=user, activity__slug__startswith="demo-"
            ).select_related(
                "activity", "activity__space", "activity__owner_profile", "occurrence"
            ).order_by("id")[:max(30, args.count * 10)])
            # Only canonical fulfilled journeys or accepted AccessUses qualify.
            completed = 0
            issued = 0
            for journey in journeys:
                accepted = journey.accesses.filter(
                    uses__result=AccessUseResult.ACCEPTED
                ).exists()
                fulfilled = journey.status == JourneyStatus.FULFILLED
                if "proofs" in domains and completed < args.count:
                    proof_type = (
                        ProofType.JOURNEY_COMPLETED if fulfilled else
                        ProofType.ACCESS_USED if accepted else None
                    )
                    if proof_type is not None:
                        if Proof.objects.filter(
                            journey=journey, subject_profile=user,
                            proof_type=proof_type,
                        ).exists():
                            counters["proofs_existing"] += 1
                        else:
                            completed += 1
                            counters["proofs_planned"] += 1
                            if args.apply:
                                try:
                                    with transaction.atomic():
                                        issue_proof(
                                            journey=journey, proof_type=proof_type,
                                            actor=None, is_public=False,
                                        )
                                    counters["proofs_created"] += 1
                                except (ValidationError, PermissionDenied):
                                    counters["proofs_rejected"] += 1

                if "credentials" in domains and issued < args.count:
                    kind = (
                        CredentialType.COMPLETION if fulfilled else
                        CredentialType.PARTICIPATION if accepted else None
                    )
                    if kind is None:
                        continue
                    activity = journey.activity
                    actor = activity.owner_profile or (
                        activity.space.created_by if activity.space_id else None
                    )
                    if actor is None or not actor.is_active:
                        counters["credentials_no_issuer"] += 1
                        continue
                    title = (
                        "Certificat de complétion" if fulfilled else
                        "Attestation de participation"
                    ) + " - " + activity.title
                    title = title[:220]
                    if Credential.objects.filter(
                        subject_profile=user, journey=journey,
                        credential_type=kind, title=title,
                    ).exists():
                        counters["credentials_existing"] += 1
                        continue
                    from trust.credential_services import can_issue_credential
                    if not can_issue_credential(actor=actor, activity=activity):
                        counters["credentials_no_authority"] += 1
                        continue
                    issued += 1
                    counters["credentials_planned"] += 1
                    if args.apply:
                        try:
                            with transaction.atomic():
                                issue_credential(
                                    activity=activity, subject_profile=user,
                                    credential_type=kind, actor=actor,
                                    journey=journey, title=title,
                                )
                            counters["credentials_created"] += 1
                        except (ValidationError, PermissionDenied):
                            counters["credentials_rejected"] += 1
            # Generic demonstration attestations are deliberate canonical
            # issuer decisions. They assert neither completion nor participation.
            if "credentials" in domains and issued < args.count:
                from activities.models import Activity, ActivityStatus
                from trust.credential_services import can_issue_credential
                candidate_activities = Activity.objects.filter(
                    slug__startswith="demo-", status=ActivityStatus.PUBLISHED
                ).select_related("space", "space__created_by", "owner_profile").order_by(
                    "id"
                )[:500]
                for activity in candidate_activities:
                    if issued >= args.count:
                        break
                    actor = activity.owner_profile or (
                        activity.space.created_by if activity.space_id else None
                    )
                    if actor is None or not actor.is_active:
                        continue
                    if not can_issue_credential(actor=actor, activity=activity):
                        continue
                    title = ("Attestation de démonstration - " + activity.title)[:220]
                    if Credential.objects.filter(
                        subject_profile=user, activity=activity,
                        credential_type=CredentialType.ATTESTATION,
                        title=title, status="issued"
                    ).exists():
                        counters["credentials_existing"] += 1
                        continue
                    issued += 1
                    counters["credentials_planned"] += 1
                    if args.apply:
                        try:
                            with transaction.atomic():
                                issue_credential(
                                    activity=activity, subject_profile=user,
                                    credential_type=CredentialType.ATTESTATION,
                                    actor=actor, title=title,
                                    statement="Attestation fictive émise dans l'univers de démonstration Makolo.",
                                )
                            counters["credentials_created"] += 1
                        except (ValidationError, PermissionDenied):
                            counters["credentials_rejected"] += 1

    print("RESOURCES", "APPLY" if args.apply else "PREVIEW",
          dict(sorted(counters.items())))
    print("Private files only. No external fetch, fabricated Proof or invented issuer authority.")


if __name__ == "__main__":
    main()
