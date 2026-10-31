"""Owner-only Web editor for the same Profile visibility service as the API."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from accounts.models import ProfileVisibilityTargetKind as Target
from accounts.profile_visibility import replace_profile_visibility
from accounts.profile_visibility_projection import build_profile_visibility_settings
from topics.models import ProfileInterest, ProfileOpenTo


class ProfilePassportVisibilityView(LoginRequiredMixin, TemplateView):
    template_name = "sharing/passport_visibility.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = build_profile_visibility_settings(self.request.user)
        labels = {
            "name": "Nom", "avatar": "Photo", "bio": "À propos",
            "profession": "Profession", "city": "Ville", "country": "Pays",
            "company_name": "Entreprise", "organization_name": "Organisation",
            "website": "Site web", "linkedin_url": "LinkedIn",
            "facebook_url": "Facebook", "instagram_url": "Instagram",
            "tiktok_url": "TikTok", "x_url": "X", "youtube_url": "YouTube",
        }
        fields = [
            {"kind": Target.FIELD, "id": key, "label": labels.get(key, key), **settings}
            for key, settings in data["fields"].items()
        ]
        interests = [
            {"kind": Target.INTEREST, **item} for item in data["interests"]
        ]
        open_to = [
            {"kind": Target.OPEN_TO, **item} for item in data["open_to"]
        ]
        all_options = [
            {"kind": "public", "label": "Tout le monde"},
            {"kind": "my_collectives", "label": "Mes collectifs"},
        ]
        for family in ("spaces", "teams", "groups"):
            all_options.extend(data["collectives"][family])
        for item in fields + interests + open_to:
            selected = {
                (rule["kind"], rule.get("id", ""))
                for rule in item["audiences"]
            }
            item["options"] = [
                {
                    **option, "value": option["kind"] + (
                        ":" + option["id"] if option.get("id") else ""
                    ),
                    "selected": (option["kind"], option.get("id", "")) in selected,
                }
                for option in all_options
            ]
            item["selected_people"] = [
                {
                    "id": rule["id"],
                    "label": rule.get("label", "Personne choisie"),
                }
                for rule in item["audiences"]
                if rule["kind"] == "selected_profile"
            ]
        context.update({"fields": fields, "interests": interests, "open_to": open_to})
        return context

    def post(self, request, *args, **kwargs):
        kind = request.POST.get("target_kind", "")
        target_id = request.POST.get("target_id", "")
        if kind == Target.FIELD:
            details = {"field_key": target_id}
        elif kind == Target.INTEREST:
            details = {"interest": get_object_or_404(
                ProfileInterest, pk=target_id, profile=request.user,
            )}
        elif kind == Target.OPEN_TO:
            details = {"open_to": get_object_or_404(
                ProfileOpenTo, pk=target_id, profile=request.user,
            )}
        else:
            messages.error(request, "Information inconnue.")
            return redirect("sharing:passport-visibility")

        audiences = []
        for value in request.POST.getlist("audience"):
            selected_kind, sep, selected_id = value.partition(":")
            audiences.append({
                "kind": selected_kind,
                **({"id": selected_id} if sep else {}),
            })
        username = request.POST.get("person_username", "").strip().lstrip("@")
        if username:
            person = get_user_model().objects.filter(
                username__iexact=username, is_active=True,
            ).first()
            if person:
                if not any(
                    row["kind"] == "selected_profile" and row.get("id") == str(person.pk)
                    for row in audiences
                ):
                    # An explicit person choice replaces the public default.
                    audiences = [row for row in audiences if row["kind"] != "public"]
                    audiences.append({"kind": "selected_profile", "id": str(person.pk)})
            else:
                messages.error(request, "Cette personne Makolo est introuvable.")
                return redirect("sharing:passport-visibility")

        try:
            replace_profile_visibility(
                owner=request.user, target_kind=kind,
                audiences=audiences, **details,
            )
            messages.success(request, "Confidentialité mise à jour.")
        except (ValidationError, ValueError, TypeError):
            messages.error(request, "Ces choix de confidentialité ne sont pas valides.")
        return redirect("sharing:passport-visibility")
