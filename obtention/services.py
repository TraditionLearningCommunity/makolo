from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility
from activities.services import create_activity, update_activity_common
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.plan_services import (
    create_journey_plan_template,
    materialize_journey_plan,
    publish_journey_plan_template,
)
from journeys.services import confirm_journey, create_journey, fulfill_journey, submit_journey
from readiness import ReadinessStatus, resolve_journey_readiness

from .models import (
    FulfillmentTargetRule,
    ObtentionConfiguration,
    ObtentionConfigurationStatus,
    ObtentionDetails,
    ObtentionJourneyContext,
    ObtentionMode,
    ObtentionModeCode,
    ObtentionTarget,
    ObtentionTargetReceipt,
)
from .selectors import fulfillment_for_journey


SUPPORTED_WORKFLOWS = {
    WorkflowKind.FULFILLMENT,
    WorkflowKind.PURCHASE,
    WorkflowKind.ORDER_APPROVAL,
    WorkflowKind.RESERVATION,
}


def _decimal(value, *, field):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "La quantité est invalide."}) from exc
    return result


def _require_authenticated(actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Vous devez être connecté.")


def _require_manage(actor, obtention):
    _require_authenticated(actor)
    if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=obtention.activity):
        raise PermissionDenied("Vous ne pouvez pas gérer cette Obtention.")


def _validate_targets_and_modes(*, targets, modes, target_rule, minimum_targets):
    if not targets:
        raise ValidationError({"targets": "Une Obtention exige au moins une cible."})
    if not modes:
        raise ValidationError({"modes": "Une Obtention exige au moins un mode admissible."})
    if target_rule == FulfillmentTargetRule.AT_LEAST_N:
        if not minimum_targets or minimum_targets < 1:
            raise ValidationError({"minimum_targets": "Indiquez le nombre minimal de cibles."})
        if minimum_targets > len(targets):
            raise ValidationError({"minimum_targets": "Le nombre minimal ne peut pas dépasser le nombre de cibles."})


def _create_configuration(
    *,
    obtention,
    actor,
    result_label,
    targets,
    modes,
    target_rule=FulfillmentTargetRule.ALL,
    minimum_targets=None,
    beneficiary_confirmation_required=True,
    operator_confirmation_required=False,
    plan_steps=None,
):
    targets = list(targets)
    modes = list(modes)
    _validate_targets_and_modes(
        targets=targets,
        modes=modes,
        target_rule=target_rule,
        minimum_targets=minimum_targets,
    )
    latest = (
        ObtentionConfiguration.objects.select_for_update()
        .filter(obtention=obtention)
        .order_by("-version")
        .first()
    )
    plan_template = None
    if plan_steps:
        plan_template = create_journey_plan_template(
            activity=obtention.activity,
            key="obtention-default",
            name=f"{obtention.activity.title} — parcours",
            steps=plan_steps,
            actor=actor,
        )
        plan_template = publish_journey_plan_template(
            template=plan_template,
            actor=actor,
        )
    configuration = ObtentionConfiguration(
        obtention=obtention,
        version=(latest.version + 1) if latest else 1,
        result_label=result_label,
        target_rule=target_rule,
        minimum_targets=minimum_targets,
        beneficiary_confirmation_required=beneficiary_confirmation_required,
        operator_confirmation_required=operator_confirmation_required,
        journey_plan_template=plan_template,
        created_by=actor,
    )
    configuration.save()

    for position, item in enumerate(targets):
        target = ObtentionTarget(
            configuration=configuration,
            title=item["title"],
            description=item.get("description", ""),
            characteristics=item.get("characteristics", {}),
            quantity=item.get("quantity", Decimal("1")),
            unit=item.get("unit", ""),
            position=item.get("position", position),
        )
        target.save()

    seen_modes = set()
    for position, item in enumerate(modes):
        if isinstance(item, str):
            code, label = item, ""
            item_position = position
        else:
            code = item["code"]
            label = item.get("label", "")
            item_position = item.get("position", position)
        if code not in ObtentionModeCode.values:
            raise ValidationError({"modes": f"Mode d'Obtention inconnu: {code}."})
        if code in seen_modes:
            raise ValidationError({"modes": "Un mode ne peut apparaître qu'une fois par configuration."})
        seen_modes.add(code)
        ObtentionMode.objects.create(
            configuration=configuration,
            code=code,
            label=label,
            position=item_position,
        )
    return configuration


@transaction.atomic
def publish_configuration(*, configuration, actor):
    configuration = (
        ObtentionConfiguration.objects.select_for_update()
        .select_related("obtention__activity")
        .prefetch_related("targets", "modes")
        .get(pk=configuration.pk)
    )
    _require_manage(actor, configuration.obtention)
    if configuration.status == ObtentionConfigurationStatus.PUBLISHED:
        return configuration
    if configuration.status != ObtentionConfigurationStatus.DRAFT:
        raise ValidationError("Seule une configuration brouillon peut être publiée.")
    targets = list(configuration.targets.all())
    modes = list(configuration.modes.all())
    _validate_targets_and_modes(
        targets=targets,
        modes=modes,
        target_rule=configuration.target_rule,
        minimum_targets=configuration.minimum_targets,
    )
    now = timezone.now()
    previous = (
        ObtentionConfiguration.objects.select_for_update()
        .filter(
            obtention=configuration.obtention,
            status=ObtentionConfigurationStatus.PUBLISHED,
        )
        .exclude(pk=configuration.pk)
        .first()
    )
    if previous:
        previous.status = ObtentionConfigurationStatus.RETIRED
        previous.retired_at = now
        previous.save(update_fields=["status", "retired_at", "updated_at"])
    configuration.status = ObtentionConfigurationStatus.PUBLISHED
    configuration.published_at = now
    configuration.save(update_fields=["status", "published_at", "updated_at"])
    return configuration


@transaction.atomic
def create_obtention(
    *,
    actor,
    title,
    targets,
    modes,
    result_label,
    space=None,
    short_description="",
    description="",
    status=ActivityStatus.DRAFT,
    visibility=ActivityVisibility.PUBLIC,
    target_rule=FulfillmentTargetRule.ALL,
    minimum_targets=None,
    beneficiary_confirmation_required=True,
    operator_confirmation_required=False,
):
    _require_authenticated(actor)
    if space is not None and not can(
        actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space=space
    ):
        raise PermissionDenied("Vous ne pouvez pas créer une Obtention au nom de cet Espace.")
    activity = create_activity(
        created_by=actor,
        title=title,
        space=space,
        owner_profile=None if space is not None else actor,
        short_description=(short_description or "").strip(),
        description=(description or "").strip(),
        status=status,
        visibility=visibility,
    )
    obtention = ObtentionDetails.objects.create(activity=activity)
    configuration = _create_configuration(
        obtention=obtention,
        actor=actor,
        result_label=result_label,
        targets=targets,
        modes=modes,
        target_rule=target_rule,
        minimum_targets=minimum_targets,
        beneficiary_confirmation_required=beneficiary_confirmation_required,
        operator_confirmation_required=operator_confirmation_required,
        plan_steps=plan_steps,
    )
    publish_configuration(configuration=configuration, actor=actor)
    return obtention


@transaction.atomic
def revise_obtention(
    *,
    obtention,
    actor,
    title,
    targets,
    modes,
    result_label,
    short_description="",
    description="",
    status=None,
    visibility=None,
    target_rule=FulfillmentTargetRule.ALL,
    minimum_targets=None,
    beneficiary_confirmation_required=True,
    operator_confirmation_required=False,
):
    obtention = (
        ObtentionDetails.objects.select_for_update()
        .select_related("activity")
        .get(pk=obtention.pk)
    )
    _require_manage(actor, obtention)
    activity_fields = {
        "title": (title or "").strip(),
        "short_description": (short_description or "").strip(),
        "description": (description or "").strip(),
    }
    if status is not None:
        activity_fields["status"] = status
    if visibility is not None:
        activity_fields["visibility"] = visibility
    update_activity_common(activity=obtention.activity, **activity_fields)
    configuration = _create_configuration(
        obtention=obtention,
        actor=actor,
        result_label=result_label,
        targets=targets,
        modes=modes,
        target_rule=target_rule,
        minimum_targets=minimum_targets,
        beneficiary_confirmation_required=beneficiary_confirmation_required,
        operator_confirmation_required=operator_confirmation_required,
        plan_steps=plan_steps,
    )
    publish_configuration(configuration=configuration, actor=actor)
    return obtention


def _can_enter(actor, activity):
    if activity.status != ActivityStatus.PUBLISHED:
        return False
    if activity.visibility in {ActivityVisibility.PUBLIC, ActivityVisibility.UNLISTED}:
        return True
    if activity.owner_profile_id == getattr(actor, "pk", None):
        return True
    return can(actor, PermissionCode.ACTIVITY_VIEW, activity=activity)


@transaction.atomic
def create_obtention_journey(
    *,
    obtention,
    actor,
    mode,
    beneficiary=None,
    occurrence=None,
    workflow=WorkflowKind.FULFILLMENT,
    expires_at=None,
):
    _require_authenticated(actor)
    obtention = (
        ObtentionDetails.objects.select_related("activity")
        .select_for_update()
        .get(pk=obtention.pk)
    )
    if not _can_enter(actor, obtention.activity):
        raise PermissionDenied("Cette Obtention n'est pas accessible dans ce contexte.")
    configuration = (
        ObtentionConfiguration.objects.select_for_update()
        .filter(
            obtention=obtention,
            status=ObtentionConfigurationStatus.PUBLISHED,
        )
        .prefetch_related("targets", "modes")
        .first()
    )
    if configuration is None:
        raise ValidationError("Cette Obtention n'a pas de configuration publiée.")
    if isinstance(mode, ObtentionMode):
        selected_mode = mode
    else:
        selected_mode = configuration.modes.filter(code=mode).first()
    if selected_mode is None or selected_mode.configuration_id != configuration.pk:
        raise ValidationError({"mode": "Ce mode n'est pas disponible pour cette Obtention."})
    if workflow not in SUPPORTED_WORKFLOWS:
        raise ValidationError({"workflow": "Ce workflow n'est pas compatible avec Obtention."})
    if occurrence is not None and occurrence.activity_id != obtention.activity_id:
        raise ValidationError({"occurrence": "L'Occurrence doit appartenir à cette Obtention."})
    beneficiary = beneficiary or actor
    if beneficiary.pk != actor.pk and not can(
        actor, PermissionCode.ACTIVITY_MANAGE, activity=obtention.activity
    ):
        raise PermissionDenied("Vous ne pouvez pas initier une Journey pour ce bénéficiaire.")
    journey = create_journey(
        initiated_by=actor,
        beneficiary=beneficiary,
        activity=obtention.activity,
        occurrence=occurrence,
        workflow=workflow,
        expires_at=expires_at,
    )
    context = ObtentionJourneyContext.objects.create(
        journey=journey,
        configuration=configuration,
        mode=selected_mode,
    )
    if configuration.journey_plan_template_id:
        materialize_journey_plan(
            journey=journey,
            template=configuration.journey_plan_template,
            actor=actor,
        )
        context.plan_materialized_at = timezone.now()
        context.save(update_fields=["plan_materialized_at"])
    return journey


@transaction.atomic
def activate_obtention_journey(*, journey, actor):
    journey = Journey.objects.select_for_update().select_related(
        "obtention_context", "activity"
    ).get(pk=journey.pk)
    if journey.beneficiary_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul le bénéficiaire peut démarrer cette démarche.")
    if journey.status != JourneyStatus.DRAFT:
        return journey
    if journey.workflow == WorkflowKind.PURCHASE:
        return confirm_journey(journey=journey, actor=actor, reason="obtention_started")
    submitted = submit_journey(journey=journey, actor=actor, reason="obtention_started")
    if submitted.workflow == WorkflowKind.FULFILLMENT:
        return confirm_journey(
            journey=submitted,
            actor=actor,
            reason="obtention_auto_confirmed",
        )
    return submitted


def _locked_receipt(journey, target):
    receipt = (
        ObtentionTargetReceipt.objects.select_for_update()
        .filter(journey=journey, target=target)
        .first()
    )
    if receipt is None:
        receipt = ObtentionTargetReceipt(journey=journey, target=target)
    return receipt


def _validate_receipt_target(journey, target):
    try:
        context = journey.obtention_context
    except ObtentionJourneyContext.DoesNotExist as exc:
        raise ValidationError("Cette Journey n'est pas une Journey Obtention.") from exc
    if target.configuration_id != context.configuration_id:
        raise ValidationError({"target": "Cette cible n'appartient pas au contrat de la Journey."})


@transaction.atomic
def record_beneficiary_receipt(*, journey, target, actor, received_quantity):
    journey = Journey.objects.select_for_update().select_related(
        "obtention_context__configuration"
    ).get(pk=journey.pk)
    if journey.beneficiary_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul le bénéficiaire peut confirmer ce qu'il a reçu.")
    if journey.status not in {JourneyStatus.CONFIRMED, JourneyStatus.IN_PROGRESS}:
        raise ValidationError("La Journey doit être confirmée avant de constater la réception.")
    _validate_receipt_target(journey, target)
    quantity = _decimal(received_quantity, field="received_quantity")
    if quantity < 0:
        raise ValidationError({"received_quantity": "La quantité reçue ne peut pas être négative."})
    receipt = _locked_receipt(journey, target)
    receipt.received_quantity = quantity
    receipt.beneficiary_confirmed_at = timezone.now()
    receipt.updated_by = actor
    receipt.save()
    return receipt


@transaction.atomic
def record_operator_receipt(*, journey, target, actor, received_quantity=None):
    journey = Journey.objects.select_for_update().select_related(
        "activity", "activity__obtention_details", "obtention_context__configuration"
    ).get(pk=journey.pk)
    obtention = journey.activity.obtention_details
    _require_manage(actor, obtention)
    if journey.status not in {JourneyStatus.CONFIRMED, JourneyStatus.IN_PROGRESS}:
        raise ValidationError("La Journey doit être confirmée avant la validation du porteur.")
    _validate_receipt_target(journey, target)
    receipt = _locked_receipt(journey, target)
    if received_quantity is not None:
        quantity = _decimal(received_quantity, field="received_quantity")
        if quantity < 0:
            raise ValidationError({"received_quantity": "La quantité reçue ne peut pas être négative."})
        receipt.received_quantity = quantity
    receipt.operator_confirmed_at = timezone.now()
    receipt.operator_confirmed_by = actor
    receipt.updated_by = actor
    receipt.save()
    return receipt


def validate_obtention_fulfillment(journey):
    result = fulfillment_for_journey(journey)
    if not result.complete:
        raise ValidationError("Le contrat d'accomplissement de cette Obtention n'est pas encore satisfait.")
    readiness = resolve_journey_readiness(journey)
    if readiness.status != ReadinessStatus.READY:
        raise ValidationError("Cette Journey n'est pas prête à être clôturée.")
    return result


@transaction.atomic
def fulfill_obtention_journey(*, journey, actor):
    journey = Journey.objects.select_for_update().select_related(
        "activity",
        "obtention_context__configuration",
        "obtention_context__mode",
    ).prefetch_related(
        "obtention_context__configuration__targets",
        "obtention_target_receipts",
        "requests",
        "steps__assignments",
        "steps__dependencies__depends_on",
        "blockers",
        "payment_obligations",
        "capacity_reservations__pool",
        "accesses",
        "form_requests__form_version__form",
        "form_requests__response",
    ).get(pk=journey.pk)
    if journey.status == JourneyStatus.FULFILLED:
        return journey
    is_beneficiary = journey.beneficiary_id == getattr(actor, "pk", None)
    is_manager = can(actor, PermissionCode.ACTIVITY_MANAGE, activity=journey.activity)
    if not (is_beneficiary or is_manager):
        raise PermissionDenied("Vous ne pouvez pas clôturer cette Journey.")
    if journey.status != JourneyStatus.CONFIRMED:
        raise ValidationError("La Journey doit être confirmée avant son accomplissement.")
    validate_obtention_fulfillment(journey)
    return fulfill_journey(journey=journey, actor=actor, reason="obtention_fulfillment_satisfied")
