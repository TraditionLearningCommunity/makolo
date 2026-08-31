from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from requirements.contracts import RequirementAssessmentState, RequirementMode
from subscriptions.contracts import RequirementDisclosure, RequirementFailurePolicy, RequirementPhase
from subscriptions.eligibility_models import EntitlementRequirement, PlanRequirement
from subscriptions.evaluators import evaluator_definitions
from subscriptions.models import FeatureDefinition, PlanBenefit, PlanEntitlement, PlanVersion, SubscriptionPlan


INPUT_CLASS = "w-full rounded-xl border px-3 py-2 text-sm"


def _style_fields(form):
    for field in form.fields.values():
        current = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = f"{current} {INPUT_CLASS}".strip()


def _evaluator_choices():
    return [("", "Aucun evaluator")] + [(definition.key, definition.key) for definition in evaluator_definitions()]


def _operator_choices():
    operators = []
    for definition in evaluator_definitions():
        for operator in definition.operators:
            if operator not in operators:
                operators.append(operator)
    return [("", "Aucun opérateur")] + [(value, value) for value in operators]


def _normalize_requirement_config(*, evaluator_key, operator, threshold):
    if not evaluator_key:
        if operator or threshold is not None:
            raise ValidationError("Un opérateur ou une valeur exige un evaluator connu.")
        return {}
    definition = next((item for item in evaluator_definitions() if item.key == evaluator_key), None)
    if definition is None:
        raise ValidationError("Evaluator Subscription inconnu.")
    config = {}
    if definition.operators:
        if not operator:
            raise ValidationError("Cet evaluator exige un opérateur.")
        config["operator"] = operator
    if "value" in definition.parameter_schema:
        if threshold is None:
            raise ValidationError("Cet evaluator exige une valeur de comparaison.")
        config["value"] = threshold
    return config


def _parse_entitlement_value(feature, raw):
    if feature.value_type == "boolean":
        normalized = (raw or "").strip().lower()
        if normalized not in {"true", "false", "1", "0", "oui", "non"}:
            raise ValidationError("Saisissez oui/non ou true/false pour une Feature booléenne.")
        value = normalized in {"true", "1", "oui"}
    elif feature.value_type == "integer":
        try:
            value = int((raw or "").strip())
        except (TypeError, ValueError) as exc:
            raise ValidationError("Saisissez un entier.") from exc
    else:
        value = (raw or "").strip()
    return feature.normalize_entitlement_value(value)


class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ["code", "plan_type", "subject_type", "is_default", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class PlanVersionForm(forms.ModelForm):
    class Meta:
        model = PlanVersion
        fields = [
            "name",
            "short_description",
            "description",
            "catalog_visibility",
            "acquisition_mode",
            "display_order",
            "change_summary",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "change_summary": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class PlanBenefitForm(forms.ModelForm):
    class Meta:
        model = PlanBenefit
        fields = ["title", "description", "icon", "position", "is_highlighted"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class PlanEntitlementForm(forms.Form):
    feature = forms.ModelChoiceField(queryset=FeatureDefinition.objects.none())
    value = forms.CharField(max_length=240, help_text="Booléen, nombre ou valeur enum selon la Feature.")

    def __init__(self, *args, plan_version, **kwargs):
        self.plan_version = plan_version
        super().__init__(*args, **kwargs)
        feature_filter = {"is_active": True}
        if plan_version.plan.subject_type == "profile":
            feature_filter["supports_profile"] = True
        else:
            feature_filter["supports_space"] = True
        self.fields["feature"].queryset = FeatureDefinition.objects.filter(**feature_filter).order_by("domain", "name", "code")
        _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        feature = cleaned.get("feature")
        if feature is None:
            return cleaned
        try:
            cleaned["normalized_value"] = _parse_entitlement_value(feature, cleaned.get("value"))
        except ValidationError as exc:
            self.add_error("value", exc)
        return cleaned


class RequirementFormBase(forms.Form):
    mode = forms.ChoiceField(choices=RequirementMode.choices)
    evaluator_key = forms.ChoiceField(choices=_evaluator_choices(), required=False)
    operator = forms.ChoiceField(choices=_operator_choices(), required=False)
    threshold = forms.IntegerField(required=False, min_value=0, label="Valeur de comparaison")
    mandatory = forms.BooleanField(required=False, initial=True)
    disclosure = forms.ChoiceField(choices=RequirementDisclosure.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        evaluator_key = cleaned.get("evaluator_key") or ""
        if mode == RequirementMode.AUTOMATIC and not evaluator_key:
            self.add_error("evaluator_key", "Un Requirement automatique exige un evaluator connu.")
            return cleaned
        try:
            cleaned["config"] = _normalize_requirement_config(
                evaluator_key=evaluator_key,
                operator=cleaned.get("operator") or "",
                threshold=cleaned.get("threshold"),
            )
        except ValidationError as exc:
            self.add_error("evaluator_key", exc)
        return cleaned


class PlanRequirementForm(RequirementFormBase):
    key = forms.SlugField(max_length=120)
    title = forms.CharField(max_length=180)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    phase = forms.ChoiceField(choices=RequirementPhase.choices)
    position = forms.IntegerField(min_value=0, initial=0)
    failure_policy = forms.ChoiceField(choices=RequirementFailurePolicy.choices)
    grace_period_days = forms.IntegerField(required=False, min_value=0, max_value=3650)


class EntitlementRequirementForm(RequirementFormBase):
    key = forms.SlugField(max_length=120)
    title = forms.CharField(max_length=180)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    position = forms.IntegerField(min_value=0, initial=0)


class EntitlementGrantForm(forms.Form):
    feature = forms.ModelChoiceField(queryset=FeatureDefinition.objects.none())
    value = forms.CharField(max_length=240)
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    valid_until = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, *args, subscription, **kwargs):
        self.subscription = subscription
        super().__init__(*args, **kwargs)
        feature_filter = {"is_active": True}
        if subscription.profile_id:
            feature_filter["supports_profile"] = True
        else:
            feature_filter["supports_space"] = True
        self.fields["feature"].queryset = FeatureDefinition.objects.filter(**feature_filter).order_by("domain", "name", "code")
        _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        feature = cleaned.get("feature")
        if feature is not None:
            try:
                cleaned["normalized_value"] = _parse_entitlement_value(feature, cleaned.get("value"))
            except ValidationError as exc:
                self.add_error("value", exc)
        return cleaned


class GrantRevokeForm(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class SubscriptionReviewForm(forms.Form):
    state = forms.ChoiceField(
        choices=[
            (RequirementAssessmentState.SATISFIED, "Approuver"),
            (RequirementAssessmentState.UNSATISFIED, "Refuser"),
            (RequirementAssessmentState.NOT_APPLICABLE, "Non applicable"),
        ]
    )
    reason_code = forms.SlugField(max_length=160, initial="subscription.review.staff_decision")
    note = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)
