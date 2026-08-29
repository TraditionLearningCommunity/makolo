from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import NotificationPreference, User
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactSensitivity,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyNote,
    JourneyNoteVisibility,
    JourneyStep,
    JourneyStepKind,
    JourneyStepOrigin,
    JourneyStepStatus,
)
from journeys.collaboration_services import create_artifact
from journeys.models import Journey, JourneyStatus, WorkflowKind
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
    OpportunitySource,
    OpportunitySourceCheck,
    OpportunitySourceCheckResult,
    OpportunitySourceStatus,
    OpportunitySourceType,
)
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from payments.models import (
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from payments.obligation_services import create_payment_obligation
from services.models import OpportunityPolicy, ServiceCurrentOutcome, ServiceDetails, ServiceJourneyContext, ServiceKind

from .common import SeedContext, stable_uuid, upsert


T34B_PERSONAS = {
    "service_manager": "beta.service.manager@makolo.test",
    "service_facilitator": "beta.service.facilitator@makolo.test",
    "service_reviewer": "beta.service.reviewer@makolo.test",
    "same_space_no_authority": "beta.service.same-space@makolo.test",
    "unrelated": "beta.service.unrelated@makolo.test",
    "opportunity_curator": "beta.opportunity.curator@makolo.test",
}


def _persona(ctx, key, first, last):
    user = upsert(
        User,
        f"task34b-{key}",
        defaults={
            "email": T34B_PERSONAS[key],
            "username": f"beta_t34b_{key}",
            "first_name": first,
            "last_name": last,
            "language": "fr",
            "timezone": "Africa/Lubumbashi",
            "is_active": True,
            "is_verified": True,
            "email_verified": True,
            "onboarding_completed": True,
            "onboarding_step": 5,
            "metadata": {"seed": "makolo-beta", "persona": f"t34b-{key}"},
        },
    )
    user.set_password(ctx.demo_password)
    user.save(update_fields=["password"])
    NotificationPreference.objects.update_or_create(
        user=user,
        defaults={
            "email_notifications": False,
            "sms_notifications": False,
            "push_notifications": False,
            "marketing_notifications": False,
            "security_notifications": True,
            "event_notifications": True,
            "service_notifications": True,
            "opportunity_notifications": True,
        },
    )
    return user


def _artifact(*, journey, uploader, kind, title, sensitivity, filename, body):
    existing = JourneyArtifact.objects.filter(journey=journey, kind=kind, title=title, version=1).first()
    if existing:
        return existing
    return create_artifact(
        journey=journey,
        uploaded_file=SimpleUploadedFile(
            filename,
            b"%PDF-1.4\n" + body + b"\n%%EOF",
            content_type="application/pdf",
        ),
        uploaded_by=uploader,
        kind=kind,
        title=title,
        sensitivity=sensitivity,
    )


def _published_opportunity_pair(ctx, curator):
    opportunity, _ = Opportunity.objects.get_or_create(
        pk=stable_uuid("task34b-opportunity"),
        defaults={"kind": OpportunityKind.JOB, "created_by": curator},
    )
    published_at = ctx.as_of - timedelta(days=10)
    revision1, created = OpportunityRevision.objects.get_or_create(
        pk=stable_uuid("task34b-opportunity-revision-1"),
        defaults={
            "opportunity": opportunity,
            "version": 1,
            "title": "Programme carrière T34B — version 1",
            "summary": "Version pinnée par un dossier Services bêta.",
            "issuer_name": "Institution Démo T34B",
            "opens_at": ctx.as_of - timedelta(days=5),
            "deadline_at": ctx.as_of + timedelta(days=14),
            "timezone": "Africa/Lubumbashi",
            "created_by": curator,
        },
    )
    if created or revision1.published_at is None:
        revision1.published_at = published_at
        revision1._allow_publication = True
        revision1.save(update_fields=["published_at"])
    revision2, created = OpportunityRevision.objects.get_or_create(
        pk=stable_uuid("task34b-opportunity-revision-2"),
        defaults={
            "opportunity": opportunity,
            "version": 2,
            "title": "Programme carrière T34B — version 2",
            "summary": "Nouvelle version disponible, adoption explicite requise.",
            "issuer_name": "Institution Démo T34B",
            "opens_at": ctx.as_of - timedelta(days=2),
            "deadline_at": ctx.as_of + timedelta(days=14),
            "timezone": "Africa/Lubumbashi",
            "change_summary": "Critères mis à jour pour la validation T34B.",
            "created_by": curator,
        },
    )
    if created or revision2.published_at is None:
        revision2.published_at = ctx.as_of - timedelta(days=1)
        revision2._allow_publication = True
        revision2.save(update_fields=["published_at"])
    Opportunity.objects.filter(pk=opportunity.pk).update(
        publication_status=OpportunityPublicationStatus.PUBLISHED,
        current_revision=revision2,
        published_at=published_at,
    )
    opportunity.refresh_from_db()
    source, _ = OpportunitySource.objects.get_or_create(
        pk=stable_uuid("task34b-opportunity-source"),
        defaults={
            "opportunity": opportunity,
            "source_type": OpportunitySourceType.OFFICIAL,
            "source_name": "Source officielle T34B",
            "url": "https://example.test/t34b/opportunity",
            "is_primary": False,
            "status": OpportunitySourceStatus.CHANGED,
            "discovered_at": ctx.as_of - timedelta(days=20),
            "last_checked_at": ctx.as_of - timedelta(hours=6),
        },
    )
    OpportunitySourceCheck.objects.get_or_create(
        pk=stable_uuid("task34b-opportunity-source-check"),
        defaults={
            "source": source,
            "result": OpportunitySourceCheckResult.CHANGED,
            "checked_at": ctx.as_of - timedelta(hours=6),
            "checked_by": curator,
            "fingerprint": "t34b-source-changed",
            "note": "Scénario de curation fictif, sans donnée participant.",
        },
    )
    return opportunity, revision1, revision2


def seed_task34b_extension(ctx: SeedContext, *, users: dict[str, object]) -> None:
    participant = users["participant"]
    manager = _persona(ctx, "service_manager", "Maya", "Manager")
    facilitator = _persona(ctx, "service_facilitator", "Fabrice", "Facilitateur")
    reviewer = _persona(ctx, "service_reviewer", "Ruth", "Reviewer")
    same_space = _persona(ctx, "same_space_no_authority", "Sam", "Même Espace")
    unrelated = _persona(ctx, "unrelated", "Una", "Externe")
    curator = _persona(ctx, "opportunity_curator", "Olivier", "Curator")

    space = upsert(
        Organization,
        "task34b-services-space",
        defaults={
            "name": "Services Beta T34B",
            "slug": "beta-services-t34b",
            "description": "Espace fictif pour valider les frontières Services T34B.",
            "contact_email": "services.t34b@makolo.test",
            "country": "CD",
            "city": "Lubumbashi",
            "public_profile": False,
            "verification_status": "verified",
            "created_by": manager,
        },
    )
    team = upsert(
        Team,
        "task34b-services-team",
        defaults={"organization": space, "name": "Équipe Services T34B", "is_default": True, "is_active": True},
    )
    TeamMembership.objects.update_or_create(
        team=team,
        user=same_space,
        defaults={"status": TeamMembershipStatus.ACTIVE, "invited_by": manager},
    )

    activity, _ = Activity.objects.get_or_create(
        pk=stable_uuid("task34b-services-activity"),
        defaults={
            "space": space,
            "created_by": manager,
            "title": "Accompagnement privé T34B",
            "slug": "beta-services-private-t34b",
            "short_description": "Dossiers privés Services pour tests de permissions.",
            "description": "Scénario bêta T34B.",
            "status": ActivityStatus.PUBLISHED,
            "visibility": ActivityVisibility.PRIVATE,
        },
    )
    ServiceDetails.objects.update_or_create(
        activity=activity,
        defaults={"service_kind": ServiceKind.APPLICATION_SUPPORT, "opportunity_policy": OpportunityPolicy.OPTIONAL},
    )
    grant_activity_role(profile=manager, activity=activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER, source="beta-t34b")
    grant_activity_role(profile=facilitator, activity=activity, role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR, source="beta-t34b")
    grant_activity_role(profile=reviewer, activity=activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER, source="beta-t34b")
    grant_platform_role(profile=curator, role=SystemRoleCode.OPPORTUNITY_CURATOR, source="beta-t34b")

    opportunity, revision1, revision2 = _published_opportunity_pair(ctx, curator)
    assigned, _ = Journey.objects.get_or_create(
        pk=stable_uuid("task34b-service-journey-assigned"),
        defaults={
            "initiated_by": participant,
            "beneficiary": participant,
            "activity": activity,
            "workflow": WorkflowKind.SERVICE,
            "status": JourneyStatus.IN_PROGRESS,
            "submitted_at": ctx.as_of - timedelta(days=5),
            "confirmed_at": ctx.as_of - timedelta(days=5),
            "started_at": ctx.as_of - timedelta(days=4),
            "expires_at": ctx.as_of + timedelta(days=7),
        },
    )
    ServiceJourneyContext.objects.get_or_create(
        pk=stable_uuid("task34b-service-context-assigned"),
        defaults={
            "journey": assigned,
            "opportunity": opportunity,
            "opportunity_revision": revision1,
            "objective": "Valider un dossier Services assigné et une révision N+1 disponible.",
            "current_outcome": ServiceCurrentOutcome.ACTION_REQUIRED,
        },
    )
    JourneyAssignment.objects.get_or_create(
        pk=stable_uuid("task34b-assignment-facilitator"),
        defaults={
            "journey": assigned,
            "profile": facilitator,
            "responsibility": JourneyAssignmentResponsibility.FACILITATOR,
            "status": JourneyAssignmentStatus.ACTIVE,
            "assigned_by": manager,
            "assigned_at": ctx.as_of - timedelta(days=4),
        },
    )
    JourneyAssignment.objects.get_or_create(
        pk=stable_uuid("task34b-assignment-reviewer"),
        defaults={
            "journey": assigned,
            "profile": reviewer,
            "responsibility": JourneyAssignmentResponsibility.REVIEWER,
            "status": JourneyAssignmentStatus.ACTIVE,
            "assigned_by": manager,
            "assigned_at": ctx.as_of - timedelta(days=3),
        },
    )
    step, _ = JourneyStep.objects.get_or_create(
        pk=stable_uuid("task34b-service-step-due"),
        defaults={
            "journey": assigned,
            "kind": JourneyStepKind.ACTION,
            "title": "Compléter les informations T34B",
            "status": JourneyStepStatus.READY,
            "position": 10,
            "is_required": True,
            "due_at": ctx.as_of + timedelta(days=3),
            "origin": JourneyStepOrigin.MANUAL,
            "created_by": manager,
            "status_changed_by": manager,
            "status_reason": "beta_t34b_ready",
        },
    )
    normal = _artifact(
        journey=assigned,
        uploader=participant,
        kind=JourneyArtifactKind.CV,
        title="CV normal T34B",
        sensitivity=JourneyArtifactSensitivity.NORMAL,
        filename="t34b-cv.pdf",
        body=b"T34B CV demo only",
    )
    restricted = _artifact(
        journey=assigned,
        uploader=participant,
        kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
        title="Document restreint T34B",
        sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        filename="t34b-identity.pdf",
        body=b"T34B restricted demo only",
    )
    JourneyArtifactReview.objects.get_or_create(
        pk=stable_uuid("task34b-review-requested"),
        defaults={
            "artifact": restricted,
            "reviewer": reviewer,
            "requested_by": manager,
            "status": JourneyArtifactReviewStatus.REQUESTED,
            "comment": "Commentaire interne fictif T34B.",
            "requested_at": ctx.as_of - timedelta(hours=4),
        },
    )
    JourneyNote.objects.get_or_create(
        pk=stable_uuid("task34b-internal-note"),
        defaults={
            "journey": assigned,
            "step": step,
            "author": manager,
            "visibility": JourneyNoteVisibility.INTERNAL,
            "body": "Note interne fictive T34B, invisible au bénéficiaire.",
        },
    )
    obligation = create_payment_obligation(
        journey=assigned,
        reason=PaymentObligationReason.SERVICE_PROCESS,
        label="Frais externes T34B",
        amount=Decimal("25.00"),
        currency="USD",
        processing_mode=PaymentObligationProcessingMode.EXTERNAL,
        external_payee_name="Institution Démo T34B",
        created_by=manager,
        due_at=ctx.as_of + timedelta(days=7),
        source_key="beta:t34b:payment-obligation",
    )
    receipt = _artifact(
        journey=assigned,
        uploader=participant,
        kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        title="Reçu soumis T34B",
        sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        filename="t34b-receipt.pdf",
        body=b"T34B payment receipt demo only",
    )
    PaymentEvidence.objects.get_or_create(
        pk=stable_uuid("task34b-payment-evidence"),
        defaults={
            "obligation": obligation,
            "artifact": receipt,
            "status": PaymentEvidenceStatus.SUBMITTED,
            "paid_at": ctx.as_of - timedelta(days=1),
            "submitted_by": participant,
        },
    )

    unassigned, _ = Journey.objects.get_or_create(
        pk=stable_uuid("task34b-service-journey-unassigned"),
        defaults={
            "initiated_by": participant,
            "beneficiary": participant,
            "activity": activity,
            "workflow": WorkflowKind.SERVICE,
            "status": JourneyStatus.CONFIRMED,
            "submitted_at": ctx.as_of - timedelta(days=2),
            "confirmed_at": ctx.as_of - timedelta(days=2),
        },
    )
    ServiceJourneyContext.objects.get_or_create(
        pk=stable_uuid("task34b-service-context-unassigned"),
        defaults={"journey": unassigned, "objective": "Dossier sans Assignment pour console manager."},
    )

    ctx.add("t34b_personas", len(T34B_PERSONAS))
    ctx.add("t34b_service_journeys", 2)
    ctx.add("t34b_artifacts", 3)
    ctx.add("t34b_opportunity_revisions", 2)
    ctx.add("t34b_same_space_without_authority", 1)
    ctx.add("t34b_unrelated_users", int(bool(unrelated.pk)))
    ctx.add("t34b_normal_artifact", int(bool(normal.pk)))
