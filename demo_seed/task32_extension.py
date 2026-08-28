from __future__ import annotations

from datetime import timedelta

from geography.models import Zone
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRequirement,
    OpportunityRequirementKind,
    OpportunityRevision,
    OpportunitySave,
    OpportunitySource,
    OpportunitySourceCheck,
    OpportunitySourceCheckResult,
    OpportunitySourceStatus,
    OpportunitySourceType,
    OpportunitySubmission,
    OpportunitySubmissionStatus,
    OpportunityZone,
    OpportunityZoneRole,
)
from opportunities.services import publish_opportunity_revision

from .common import SeedContext, stable_uuid


def _published_opportunity(
    *,
    ctx: SeedContext,
    key: str,
    kind: str,
    title: str,
    issuer: str,
    actor,
    zone: Zone,
    requirements: tuple[tuple[str, str], ...],
):
    opportunity, _ = Opportunity.objects.get_or_create(
        pk=stable_uuid(f"task32-opportunity:{key}"),
        defaults={"kind": kind, "created_by": actor},
    )
    revision, _ = OpportunityRevision.objects.get_or_create(
        pk=stable_uuid(f"task32-opportunity-revision:{key}:1"),
        defaults={
            "opportunity": opportunity,
            "version": 1,
            "title": title,
            "summary": "Donnée fictive Makolo pour valider Opportunities et Requirements.",
            "issuer_name": issuer,
            "opens_at": ctx.as_of,
            "deadline_at": ctx.as_of + timedelta(days=365),
            "timezone": "Africa/Lubumbashi",
            "application_instructions": "Consulter la source officielle fictive avant toute démarche.",
            "remote_allowed": kind == OpportunityKind.JOB,
            "created_by": actor,
        },
    )
    source, _ = OpportunitySource.objects.get_or_create(
        pk=stable_uuid(f"task32-opportunity-source:{key}:official"),
        defaults={
            "opportunity": opportunity,
            "source_type": OpportunitySourceType.OFFICIAL,
            "source_name": f"Source officielle fictive — {issuer}",
            "url": f"https://example.test/makolo-beta/opportunities/{key}",
            "external_reference": f"BETA-{key.upper()}",
            "is_primary": True,
            "status": OpportunitySourceStatus.ACTIVE,
            "verified_at": ctx.as_of,
            "verified_by": actor,
        },
    )
    OpportunitySourceCheck.objects.get_or_create(
        pk=stable_uuid(f"task32-opportunity-source-check:{key}:initial"),
        defaults={
            "source": source,
            "result": OpportunitySourceCheckResult.UNCHANGED,
            "checked_at": ctx.as_of,
            "checked_by": actor,
            "fingerprint": f"beta-{key}-v1",
            "note": "Contrôle fictif déterministe du seed bêta.",
        },
    )
    OpportunityZone.objects.get_or_create(
        pk=stable_uuid(f"task32-opportunity-zone:{key}:eligibility"),
        defaults={"revision": revision, "zone": zone, "role": OpportunityZoneRole.ELIGIBILITY},
    )
    for position, (requirement_kind, requirement_title) in enumerate(requirements, start=1):
        OpportunityRequirement.objects.get_or_create(
            pk=stable_uuid(f"task32-opportunity-requirement:{key}:{position}"),
            defaults={
                "revision": revision,
                "kind": requirement_kind,
                "title": requirement_title,
                "description": f"Requirement fictif de validation T32 : {requirement_title}.",
                "is_mandatory": True,
                "position": position * 10,
            },
        )
    if revision.published_at is None:
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=actor)
    else:
        opportunity.refresh_from_db()
        if opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED or opportunity.current_revision_id != revision.pk:
            raise RuntimeError(f"Opportunity bêta T32 incohérente: {key}")
    return opportunity


def seed_task32_extension(ctx: SeedContext, *, users: dict[str, object]) -> None:
    staff = users["staff"]
    participant = users["participant"]
    zone = Zone.objects.get(pk=stable_uuid("geography.zone:beta-nearby"))

    job = _published_opportunity(
        ctx=ctx,
        key="backend-job",
        kind=OpportunityKind.JOB,
        title="Développeur backend — opportunité bêta",
        issuer="Entreprise Démo Makolo",
        actor=staff,
        zone=zone,
        requirements=(
            (OpportunityRequirementKind.DOCUMENT, "CV à jour"),
            (OpportunityRequirementKind.EXPERIENCE, "Expérience backend"),
        ),
    )
    scholarship = _published_opportunity(
        ctx=ctx,
        key="scholarship",
        kind=OpportunityKind.SCHOLARSHIP,
        title="Bourse académique — opportunité bêta",
        issuer="Fondation Démo Makolo",
        actor=staff,
        zone=zone,
        requirements=(
            (OpportunityRequirementKind.EDUCATION, "Diplôme ou attestation"),
            (OpportunityRequirementKind.DOCUMENT, "Lettre de motivation"),
            (OpportunityRequirementKind.FINANCIAL, "Frais de dossier externes"),
        ),
    )

    OpportunitySave.objects.get_or_create(profile=participant, opportunity=job)
    OpportunitySave.objects.get_or_create(profile=participant, opportunity=scholarship)
    OpportunitySubmission.objects.get_or_create(
        pk=stable_uuid("task32-opportunity-submission:participant"),
        defaults={
            "submitted_by": participant,
            "url": "https://example.test/makolo-beta/opportunities/user-suggestion",
            "title": "Opportunity proposée par un participant bêta",
            "comment": "Suggestion fictive en attente de revue staff.",
            "status": OpportunitySubmissionStatus.PENDING,
        },
    )

    opportunity_ids = [job.pk, scholarship.pk]
    ctx.add("beta_opportunities", Opportunity.objects.filter(pk__in=opportunity_ids).count())
    ctx.add("beta_opportunity_requirements", OpportunityRequirement.objects.filter(revision__opportunity_id__in=opportunity_ids).count())
    ctx.add("beta_opportunity_saves", OpportunitySave.objects.filter(profile=participant, opportunity_id__in=opportunity_ids).count())
    ctx.add("beta_opportunity_submissions", OpportunitySubmission.objects.filter(pk=stable_uuid("task32-opportunity-submission:participant")).count())
