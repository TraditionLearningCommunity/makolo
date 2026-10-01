from __future__ import annotations

from datetime import timedelta

from accounts.models import User
from activities.models import ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import Journey, JourneyStatus
from organizations.models import Organization
from obtention.models import ObtentionDetails, ObtentionModeCode
from obtention.services import (
    activate_obtention_journey,
    create_obtention,
    create_obtention_journey,
)

from .beta import BETA_PERSONAS
from .common import SeedContext, upsert


def _space(owner):
    space = upsert(
        Organization,
        "beta-obtention",
        defaults={
            "name": "Makolo Beta Obtention",
            "slug": "beta-obtention",
            "description": "Espace fictif pour démontrer la verticale Obtention.",
            "contact_email": "contact.beta.obtention@makolo.test",
            "country": "CD",
            "city": "Lubumbashi",
            "public_profile": True,
            "verification_status": "verified",
            "created_by": owner,
        },
    )
    grant_space_role(
        profile=owner,
        space=space,
        role=SystemRoleCode.SPACE_OWNER,
        granted_by=owner,
        source="makolo-beta-obtention",
    )
    return space


def _ensure_obtention(*, actor, space, slug, title, targets, modes, result_label, **kwargs):
    existing = (
        ObtentionDetails.objects.select_related("activity")
        .filter(activity__space=space, activity__slug=slug)
        .first()
    )
    if existing is not None:
        return existing
    return create_obtention(
        actor=actor,
        space=space,
        title=title,
        targets=targets,
        modes=modes,
        result_label=result_label,
        status=ActivityStatus.PUBLISHED,
        visibility=ActivityVisibility.PUBLIC,
        **kwargs,
    )


def _ensure_journey(*, obtention, beneficiary, mode, occurrence=None, activate=False):
    existing = (
        Journey.objects.filter(
            beneficiary=beneficiary,
            activity=obtention.activity,
            obtention_context__mode__code=mode,
        )
        .order_by("created_at", "id")
        .first()
    )
    if existing is not None:
        return existing
    journey = create_obtention_journey(
        obtention=obtention,
        actor=beneficiary,
        beneficiary=beneficiary,
        mode=mode,
        occurrence=occurrence,
    )
    if activate:
        journey = activate_obtention_journey(journey=journey, actor=beneficiary)
    return journey


def seed_obtention(ctx: SeedContext) -> None:
    """Add idempotent, visible Obtention scenarios to the canonical beta world."""
    owner = User.objects.get(email=BETA_PERSONAS["space_admin"])
    participant = User.objects.get(email=BETA_PERSONAS["participant"])
    space = _space(owner)

    kit = _ensure_obtention(
        actor=owner,
        space=space,
        slug="kit-scolaire-a-retirer",
        title="Kit scolaire à retirer",
        short_description="Recevoir un kit scolaire complet à Lubumbashi.",
        description="Scénario bêta d’attribution réelle, indépendant du paiement.",
        targets=[
            {"title": "Sac scolaire", "quantity": "1", "unit": "pièce"},
            {"title": "Cahiers", "quantity": "10", "unit": "pièces"},
        ],
        modes=[ObtentionModeCode.RECEIVE],
        result_label="Kit scolaire effectivement remis",
        operator_confirmation_required=True,
        plan_steps=[
            {
                "key": "identity",
                "actor_kind": "beneficiary",
                "kind": "action",
                "title": "Confirmer son identité",
                "is_required": True,
            },
            {
                "key": "handover",
                "actor_kind": "operator",
                "kind": "review",
                "title": "Préparer la remise du kit",
                "depends_on": ["identity"],
                "is_required": True,
            },
        ],
        requirements=[
            {
                "key": "identity-confirmed",
                "title": "Identité confirmée",
                "mode": "action",
                "step_key": "identity",
                "is_mandatory": True,
            },
            {
                "key": "eligibility-reviewed",
                "title": "Éligibilité validée",
                "mode": "verification",
                "is_mandatory": True,
            },
        ],
    )
    pickup = upsert(
        Occurrence,
        "beta-obtention-kit-pickup",
        defaults={
            "activity": kit.activity,
            "label": "Retrait du kit",
            "start_at": (ctx.as_of + timedelta(days=7)).replace(hour=10),
            "end_at": (ctx.as_of + timedelta(days=7)).replace(hour=16),
            "timezone": "Africa/Lubumbashi",
            "status": OccurrenceStatus.SCHEDULED,
        },
    )
    _ensure_journey(
        obtention=kit,
        beneficiary=participant,
        mode=ObtentionModeCode.RECEIVE,
        occurrence=pickup,
        activate=True,
    )

    equipment = _ensure_obtention(
        actor=owner,
        space=space,
        slug="projecteur-4k",
        title="Projecteur 4K",
        short_description="Acheter ou louer un projecteur pour une activité.",
        description="Scénario bêta montrant plusieurs modes sans créer de sous-verticale Achat/Location.",
        targets=[{"title": "Projecteur 4K", "quantity": "1", "unit": "pièce"}],
        modes=[ObtentionModeCode.BUY, ObtentionModeCode.RENT],
        result_label="Projecteur effectivement obtenu",
    )
    _ensure_journey(
        obtention=equipment,
        beneficiary=participant,
        mode=ObtentionModeCode.RENT,
        activate=False,
    )

    ctx.add("beta_obtentions", 2)
    ctx.add(
        "beta_obtention_journeys",
        Journey.objects.filter(
            beneficiary=participant,
            activity__obtention_details__isnull=False,
        ).count(),
    )
