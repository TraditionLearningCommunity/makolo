import json
from decimal import Decimal, InvalidOperation

from django import forms

from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization
from journeys.models import JourneyPlanStepActor, JourneyStepKind

from .models import (
    FulfillmentTargetRule,
    ObtentionConfigurationStatus,
    ObtentionModeCode,
)
from .selectors import published_configuration


def _serialize_plan_steps(configuration):
    if configuration is None or not configuration.journey_plan_template_id:
        return ""
    rows = []
    for step in configuration.journey_plan_template.steps.prefetch_related("dependencies__depends_on").all():
        depends_on = ",".join(
            dependency.depends_on.key for dependency in step.dependencies.all()
        )
        rows.append(
            " | ".join(
                [
                    step.key,
                    step.actor_kind,
                    step.kind,
                    "yes" if step.is_required else "no",
                    str(step.relative_due_days) if step.relative_due_days is not None else "",
                    step.title,
                    depends_on,
                    step.description,
                ]
            ).rstrip(" |")
        )
    return "\n".join(rows)


def _serialize_targets(configuration):
    if configuration is None:
        return ""
    rows = []
    for target in configuration.targets.all():
        characteristics = (
            json.dumps(target.characteristics, ensure_ascii=False, separators=(",", ":"))
            if target.characteristics
            else ""
        )
        rows.append(
            " | ".join(
                [
                    target.title,
                    str(target.quantity),
                    target.unit,
                    target.description,
                    characteristics,
                ]
            ).rstrip(" |")
        )
    return "\n".join(rows)


class ObtentionConfigurationForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=220)
    short_description = forms.CharField(label="Résumé", max_length=320, required=False)
    description = forms.CharField(
        label="Description",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    space = forms.ModelChoiceField(
        label="Porteur",
        queryset=Organization.objects.none(),
        required=False,
        empty_label="Mon Profil",
    )
    modes = forms.MultipleChoiceField(
        label="Modes d'obtention",
        choices=ObtentionModeCode.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    targets = forms.CharField(
        label="Cibles",
        widget=forms.Textarea(attrs={"rows": 7}),
        help_text=(
            "Une cible par ligne : nom | quantité | unité | description | caractéristiques JSON. "
            "Seul le nom est obligatoire."
        ),
    )
    plan_steps = forms.CharField(
        label="Étapes préparées",
        required=False,
        widget=forms.Textarea(attrs={"rows": 7}),
        help_text=(
            "Optionnel. Une étape par ligne : clé | beneficiary/operator | type | yes/no | délai jours | titre | dépendances (clés séparées par virgule) | description."
        ),
    )
    result_label = forms.CharField(
        label="Quand peut-on dire « obtenu » ?",
        max_length=220,
    )
    target_rule = forms.ChoiceField(
        label="Règle sur les cibles",
        choices=FulfillmentTargetRule.choices,
        initial=FulfillmentTargetRule.ALL,
    )
    minimum_targets = forms.IntegerField(
        label="Nombre minimal de cibles",
        min_value=1,
        required=False,
    )
    beneficiary_confirmation_required = forms.BooleanField(
        label="Confirmation du bénéficiaire requise",
        required=False,
        initial=True,
    )
    operator_confirmation_required = forms.BooleanField(
        label="Validation du porteur requise",
        required=False,
    )
    status = forms.ChoiceField(
        label="État de l'Activity",
        choices=ActivityStatus.choices,
        initial=ActivityStatus.DRAFT,
    )
    visibility = forms.ChoiceField(
        label="Visibilité",
        choices=ActivityVisibility.choices,
        initial=ActivityVisibility.PUBLIC,
    )

    def __init__(self, *args, actor, obtention=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.obtention = obtention
        allowed_ids = space_ids_with_permission(
            actor, PermissionCode.SPACE_ACTIVITIES_MANAGE
        )
        spaces = Organization.objects.order_by("name")
        if allowed_ids is not None:
            spaces = spaces.filter(pk__in=allowed_ids)
        self.fields["space"].queryset = spaces
        if obtention is not None:
            activity = obtention.activity
            configuration = published_configuration(obtention)
            self.fields["space"].disabled = True
            self.initial.update(
                {
                    "title": activity.title,
                    "short_description": activity.short_description,
                    "description": activity.description,
                    "space": activity.space,
                    "modes": [mode.code for mode in configuration.modes.all()] if configuration else [],
                    "targets": _serialize_targets(configuration),
                    "plan_steps": _serialize_plan_steps(configuration),
                    "result_label": configuration.result_label if configuration else "",
                    "target_rule": configuration.target_rule if configuration else FulfillmentTargetRule.ALL,
                    "minimum_targets": configuration.minimum_targets if configuration else None,
                    "beneficiary_confirmation_required": configuration.beneficiary_confirmation_required if configuration else True,
                    "operator_confirmation_required": configuration.operator_confirmation_required if configuration else False,
                    "status": activity.status,
                    "visibility": activity.visibility,
                }
            )

    def clean_plan_steps(self):
        raw = self.cleaned_data.get("plan_steps") or ""
        steps = []
        valid_kinds = set(JourneyStepKind.values)
        valid_actors = set(JourneyPlanStepActor.values)
        seen = set()
        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|", 7)]
            if len(parts) < 6:
                raise forms.ValidationError(
                    f"Ligne {line_number} : utilisez au moins clé | acteur | type | yes/no | délai | titre."
                )
            key, actor_kind, kind, required_raw, due_raw, title = parts[:6]
            if not key or key in seen:
                raise forms.ValidationError(
                    f"Ligne {line_number} : clé d'étape absente ou dupliquée."
                )
            seen.add(key)
            if actor_kind not in valid_actors:
                raise forms.ValidationError(
                    f"Ligne {line_number} : acteur attendu beneficiary ou operator."
                )
            if kind not in valid_kinds:
                raise forms.ValidationError(
                    f"Ligne {line_number} : type d'étape inconnu."
                )
            required = required_raw.lower() not in {"no", "non", "false", "0"}
            relative_due_days = None
            if due_raw:
                try:
                    relative_due_days = int(due_raw)
                except ValueError as exc:
                    raise forms.ValidationError(
                        f"Ligne {line_number} : délai invalide."
                    ) from exc
                if relative_due_days < 0:
                    raise forms.ValidationError(
                        f"Ligne {line_number} : le délai ne peut pas être négatif."
                    )
            depends_on = []
            if len(parts) > 6 and parts[6]:
                depends_on = [value.strip() for value in parts[6].split(",") if value.strip()]
            steps.append(
                {
                    "key": key,
                    "actor_kind": actor_kind,
                    "kind": kind,
                    "is_required": required,
                    "relative_due_days": relative_due_days,
                    "title": title,
                    "depends_on": depends_on,
                    "description": parts[7] if len(parts) > 7 else "",
                }
            )
        known = {step["key"] for step in steps}
        for step in steps:
            missing = [key for key in step["depends_on"] if key not in known]
            if missing:
                raise forms.ValidationError(
                    f"Étape {step['key']} : dépendance inconnue {', '.join(missing)}."
                )
        return steps

    def clean_targets(self):
        raw = self.cleaned_data["targets"]
        targets = []
        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|", 4)]
            title = parts[0] if parts else ""
            if not title:
                raise forms.ValidationError(f"Ligne {line_number} : le nom de la cible est obligatoire.")
            quantity_raw = parts[1] if len(parts) > 1 and parts[1] else "1"
            try:
                quantity = Decimal(quantity_raw)
            except (InvalidOperation, ValueError) as exc:
                raise forms.ValidationError(f"Ligne {line_number} : quantité invalide.") from exc
            if quantity <= 0:
                raise forms.ValidationError(f"Ligne {line_number} : la quantité doit être positive.")
            characteristics = {}
            if len(parts) > 4 and parts[4]:
                try:
                    characteristics = json.loads(parts[4])
                except json.JSONDecodeError as exc:
                    raise forms.ValidationError(f"Ligne {line_number} : JSON de caractéristiques invalide.") from exc
                if not isinstance(characteristics, dict):
                    raise forms.ValidationError(f"Ligne {line_number} : les caractéristiques doivent être un objet JSON.")
            targets.append(
                {
                    "title": title,
                    "quantity": quantity,
                    "unit": parts[2] if len(parts) > 2 else "",
                    "description": parts[3] if len(parts) > 3 else "",
                    "characteristics": characteristics,
                }
            )
        if not targets:
            raise forms.ValidationError("Ajoutez au moins une cible.")
        return targets

    def clean(self):
        cleaned = super().clean()
        rule = cleaned.get("target_rule")
        minimum = cleaned.get("minimum_targets")
        targets = cleaned.get("targets") or []
        if rule == FulfillmentTargetRule.AT_LEAST_N:
            if not minimum:
                self.add_error("minimum_targets", "Indiquez le nombre minimal de cibles.")
            elif minimum > len(targets):
                self.add_error("minimum_targets", "Ce nombre dépasse le nombre de cibles.")
        elif minimum is not None:
            cleaned["minimum_targets"] = None
        return cleaned


class ReceiptForm(forms.Form):
    received_quantity = forms.DecimalField(
        label="Quantité effectivement reçue",
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0"),
    )
