from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from conversations.models import (
    ConversationContext,
    ConversationContextKind,
    ConversationDiscoverability,
    ConversationEntryMode,
    ConversationModePreset,
)
from conversations.services import activate_participation, ensure_context_conversation
from funding.models import FundingContribution, FundingDetails
from funding.services import create_funding_contribution
from organizations.models import Organization
from payments.models import PaymentObligationStatus
from payments.obligation_services import satisfy_payment_obligation

from .beta import BETA_PERSONAS
from .common import SeedContext, upsert


def _beta_users():
    from accounts.models import User

    return {key: User.objects.get(email=email) for key, email in BETA_PERSONAS.items()}


def _space(slug: str):
    return Organization.objects.get(slug=slug)


def _grant_activity_manager(*, profile, activity, granted_by):
    grant_activity_role(
        profile=profile,
        activity=activity,
        role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        granted_by=granted_by,
        source="makolo-beta-observability",
    )


def _ensure_activity_conversation(*, actor, activity, purpose_key, title, purpose, participants=()):
    _grant_activity_manager(profile=actor, activity=activity, granted_by=actor)
    conversation = ensure_context_conversation(
        actor=actor,
        kind=ConversationContextKind.ACTIVITY,
        activity=activity,
        purpose_key=purpose_key,
        separation_reason="Scénario de démonstration bêta distinct du fil de coordination principal." if purpose_key != "coordination" else "",
        title_override=title,
        purpose=purpose,
        mode_preset=ConversationModePreset.MIXED,
        entry_mode=ConversationEntryMode.DERIVED,
        discoverability=ConversationDiscoverability.ELIGIBLE,
        client_reference=f"beta:{activity.pk}:{purpose_key}",
    )
    for profile in participants:
        activate_participation(actor=actor, conversation=conversation, profile=profile)
    return conversation


def _conversations(ctx: SeedContext, users: dict[str, object]) -> None:
    paid_activity = Activity.objects.get(slug="beta-event-paid", space__slug="beta-events")
    free_activity = Activity.objects.get(slug="beta-event-free", space__slug="beta-events")
    transport_activity = Activity.objects.get(slug="beta-transport-lub-kol", space__slug="beta-transport")

    _ensure_activity_conversation(
        actor=users["event_manager"],
        activity=paid_activity,
        purpose_key="coordination",
        title="Coordination — Forum créatif Makolo",
        purpose="Préparer les décisions, confirmations et questions liées au Forum créatif Makolo.",
        participants=(users["participant"], users["marketing"], users["finance"]),
    )
    _ensure_activity_conversation(
        actor=users["event_manager"],
        activity=free_activity,
        purpose_key="accueil-participants",
        title="Accueil participants — Atelier communauté gratuit",
        purpose="Répondre aux questions utiles avant l’atelier et confirmer les informations pratiques.",
        participants=(users["participant"], users["marketing"]),
    )
    _ensure_activity_conversation(
        actor=users["transport_operator"],
        activity=transport_activity,
        purpose_key="embarquement",
        title="Coordination embarquement — Lubumbashi → Kolwezi",
        purpose="Coordonner les départs, les voyageurs et les informations de dernière minute.",
        participants=(users["participant"], users["scanner"]),
    )
    ctx.add("beta_observable_conversations", 3)


def _funding(ctx: SeedContext, users: dict[str, object]) -> None:
    event_space = _space("beta-events")
    manager = users["finance"]
    owner = users["space_admin"]
    activity = upsert(
        Activity,
        "beta-funding-stage",
        defaults={
            "space": event_space,
            "created_by": manager,
            "title": "Financer la scène du festival bêta",
            "slug": "beta-funding-stage",
            "short_description": "Réunir les moyens financiers nécessaires pour installer la scène.",
            "description": "Financement fictif qui montre objectif, montant réuni et contribution sans recréer Payments.",
            "status": ActivityStatus.PUBLISHED,
            "visibility": ActivityVisibility.PUBLIC,
        },
    )
    _grant_activity_manager(profile=manager, activity=activity, granted_by=owner)
    funding = upsert(
        FundingDetails,
        "beta-stage",
        defaults={
            "activity": activity,
            "currency": "USD",
            "target_amount": Decimal("8000.00"),
            "minimum_contribution": Decimal("2.00"),
            "maximum_contribution": None,
            "opens_at": ctx.as_of - timedelta(days=3),
            "closes_at": None,
        },
    )
    for key, profile, amount in [
        ("lead", users["participant"], Decimal("6400.00")),
        ("partner", users["marketing"], Decimal("950.00")),
    ]:
        contribution = create_funding_contribution(
            funding=funding,
            actor=profile,
            amount=amount,
            client_reference=f"beta-funding-stage-{key}",
        )
        if contribution.payment_obligation.status != PaymentObligationStatus.SATISFIED:
            satisfy_payment_obligation(obligation=contribution.payment_obligation, source="beta-seed")

    _ensure_activity_conversation(
        actor=manager,
        activity=activity,
        purpose_key="financement",
        title="Coordination financement — scène du festival bêta",
        purpose="Suivre les questions utiles sur les contributions et la clôture du financement.",
        participants=(users["participant"], users["marketing"], users["space_admin"]),
    )
    ctx.add("beta_fundings", 1)
    ctx.add("beta_funding_contributions", FundingContribution.objects.filter(funding=funding).count())


def seed_beta_observability(ctx: SeedContext) -> None:
    """Add visible demo scenarios for mature verticals without changing domain truths."""

    users = _beta_users()
    _conversations(ctx, users)
    _funding(ctx, users)
