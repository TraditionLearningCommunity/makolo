from decimal import Decimal

from rest_framework import serializers

from activities.models import ActivityStatus, ActivityVisibility
from journeys.models import JourneyPlanStepActor, JourneyStepKind, WorkflowKind
from requirements.contracts import RequirementAssessmentState, RequirementMode

from .models import FulfillmentTargetRule, ObtentionModeCode


class ObtentionTargetInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    characteristics = serializers.JSONField(required=False, default=dict)
    quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
        default=Decimal("1"),
    )
    unit = serializers.CharField(max_length=40, required=False, allow_blank=True)


class JourneyPlanStepInputSerializer(serializers.Serializer):
    key = serializers.SlugField(max_length=120)
    actor_kind = serializers.ChoiceField(
        choices=JourneyPlanStepActor.choices,
        default=JourneyPlanStepActor.BENEFICIARY,
    )
    kind = serializers.ChoiceField(
        choices=JourneyStepKind.choices,
        default=JourneyStepKind.ACTION,
    )
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    position = serializers.IntegerField(min_value=0, required=False)
    is_required = serializers.BooleanField(default=True)
    relative_due_days = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    depends_on = serializers.ListField(
        child=serializers.SlugField(max_length=120),
        required=False,
        default=list,
    )


class RequirementInputSerializer(serializers.Serializer):
    key = serializers.SlugField(max_length=120)
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True)
    mode = serializers.ChoiceField(
        choices=RequirementMode.choices,
        default=RequirementMode.VERIFICATION,
    )
    evaluator_key = serializers.CharField(max_length=120, required=False, allow_blank=True)
    evaluator_config = serializers.JSONField(required=False, default=dict)
    is_mandatory = serializers.BooleanField(default=True)
    position = serializers.IntegerField(min_value=0, required=False)
    step_key = serializers.SlugField(max_length=120, required=False, allow_blank=True)


class RequirementAssessmentInputSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=RequirementAssessmentState.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class ObtentionConfigurationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    short_description = serializers.CharField(max_length=320, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    space_id = serializers.UUIDField(required=False, allow_null=True)
    targets = ObtentionTargetInputSerializer(many=True)
    modes = serializers.ListField(
        child=serializers.ChoiceField(choices=ObtentionModeCode.choices),
        allow_empty=False,
    )
    plan_steps = JourneyPlanStepInputSerializer(many=True, required=False, default=list)
    requirements = RequirementInputSerializer(many=True, required=False, default=list)
    result_label = serializers.CharField(max_length=220)
    target_rule = serializers.ChoiceField(
        choices=FulfillmentTargetRule.choices,
        default=FulfillmentTargetRule.ALL,
    )
    minimum_targets = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    beneficiary_confirmation_required = serializers.BooleanField(default=True)
    operator_confirmation_required = serializers.BooleanField(default=False)
    status = serializers.ChoiceField(
        choices=ActivityStatus.choices,
        default=ActivityStatus.DRAFT,
    )
    visibility = serializers.ChoiceField(
        choices=ActivityVisibility.choices,
        default=ActivityVisibility.PUBLIC,
    )

    def validate_targets(self, value):
        if not value:
            raise serializers.ValidationError("Ajoutez au moins une cible.")
        return value

    def validate_modes(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Un mode ne peut apparaître qu'une fois.")
        return value

    def validate(self, attrs):
        steps = attrs.get("plan_steps") or []
        keys = [step["key"] for step in steps]
        requirement_rows = attrs.get("requirements") or []
        requirement_keys = [item["key"] for item in requirement_rows]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise serializers.ValidationError(
                {"requirements": "Les clés Requirement doivent être uniques."}
            )
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError({"plan_steps": "Les clés d'étapes doivent être uniques."})
        known = set(keys)
        for item in requirement_rows:
            step_key = item.get("step_key") or ""
            if step_key and step_key not in known:
                raise serializers.ValidationError(
                    {"requirements": f"Step inconnue pour {item['key']}: {step_key}."}
                )
            if item.get("mode") == RequirementMode.ACTION and not step_key:
                raise serializers.ValidationError(
                    {"requirements": f"Le Requirement action {item['key']} doit référencer une Step."}
                )
        for step in steps:
            missing = [key for key in step.get("depends_on", []) if key not in known]
            if missing:
                raise serializers.ValidationError(
                    {"plan_steps": f"Dépendance inconnue pour {step['key']}: {', '.join(missing)}."}
                )
        rule = attrs.get("target_rule", FulfillmentTargetRule.ALL)
        minimum = attrs.get("minimum_targets")
        targets = attrs.get("targets") or []
        if rule == FulfillmentTargetRule.AT_LEAST_N:
            if minimum is None:
                raise serializers.ValidationError(
                    {"minimum_targets": "Cette règle exige un nombre minimal."}
                )
            if minimum > len(targets):
                raise serializers.ValidationError(
                    {"minimum_targets": "Ce nombre dépasse le nombre de cibles."}
                )
        elif minimum is not None:
            attrs["minimum_targets"] = None
        return attrs


class ObtentionUpdateSerializer(ObtentionConfigurationSerializer):
    plan_steps = JourneyPlanStepInputSerializer(many=True, required=False)
    requirements = RequirementInputSerializer(many=True, required=False)
    title = serializers.CharField(max_length=220, required=False)
    targets = ObtentionTargetInputSerializer(many=True, required=False)
    modes = serializers.ListField(
        child=serializers.ChoiceField(choices=ObtentionModeCode.choices),
        allow_empty=False,
        required=False,
    )
    result_label = serializers.CharField(max_length=220, required=False)
    target_rule = serializers.ChoiceField(
        choices=FulfillmentTargetRule.choices,
        required=False,
    )
    beneficiary_confirmation_required = serializers.BooleanField(required=False)
    operator_confirmation_required = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(choices=ActivityStatus.choices, required=False)
    visibility = serializers.ChoiceField(choices=ActivityVisibility.choices, required=False)
    space_id = serializers.UUIDField(read_only=True)


class ObtentionJourneyCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ObtentionModeCode.choices)
    occurrence_id = serializers.UUIDField(required=False, allow_null=True)
    workflow = serializers.ChoiceField(
        choices=[
            WorkflowKind.FULFILLMENT,
            WorkflowKind.PURCHASE,
            WorkflowKind.ORDER_APPROVAL,
            WorkflowKind.RESERVATION,
        ],
        default=WorkflowKind.FULFILLMENT,
    )


class ReceiptSerializer(serializers.Serializer):
    received_quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0"),
    )


class OperatorReceiptSerializer(serializers.Serializer):
    received_quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
    )
