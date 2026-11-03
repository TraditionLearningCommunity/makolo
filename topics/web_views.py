from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.urls import reverse
from django.views.generic import FormView

from accounts.models import (
    ProfileVisibilityAudienceKind, ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind,
)
from accounts.profile_visibility import (
    ProfileVisibilityResolver, replace_profile_visibility,
)

from .forms import InterestSelectionForm, OpenToSettingsForm
from .models import ProfileInterest, ProfileOpenTo
from .services import replace_profile_interests, replace_profile_open_to, set_profile_interest_visibility


def _sync_existing_public_audiences(*, profile, kind, rows, published):
    """Keep basic Topics settings and Passport's explicit policies coherent.

    An unchecked public box must withdraw a saved PUBLIC policy. A previously
    restricted policy (group or person) remains restricted unless the owner
    explicitly chooses Public here. No extra policies are created.
    """
    for row in rows:
        target = {"interest": row} if kind == ProfileVisibilityTargetKind.INTEREST else {"open_to": row}
        policy = ProfileVisibilityPolicy.objects.filter(
            owner=profile, target_kind=kind, **target,
        ).first()
        if policy is None:
            continue
        was_public = policy.audiences.filter(
            kind=ProfileVisibilityAudienceKind.PUBLIC,
        ).exists()
        key = row.topic_id if kind == ProfileVisibilityTargetKind.INTEREST else row.kind
        wants_public = key in published
        if was_public == wants_public:
            continue
        replace_profile_visibility(
            owner=profile, target_kind=kind, **target,
            audiences=[{"kind": "public"}] if wants_public else [],
        )


class ProfileInterestSettingsView(LoginRequiredMixin, FormView):
    login_url = "core:login"
    template_name = "topics/interests.html"
    form_class = InterestSelectionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        rows = ProfileInterest.objects.filter(profile=self.request.user)
        initial["topics"] = list(rows.values_list("topic_id", flat=True))
        visibility = ProfileVisibilityResolver(owner=self.request.user)
        initial["public_topics"] = [
            row.topic_id for row in rows if visibility.interest(row)
        ]
        return initial

    @transaction.atomic
    def form_valid(self, form):
        selected = {topic.pk for topic in form.cleaned_data["topics"]}
        replace_profile_interests(profile=self.request.user, topic_ids=selected)
        # The visible public_topics checkbox is authoritative, including for
        # newly created Interests. JS offers public as the initial choice, but
        # cannot override an owner's explicit opt-out on the first save.
        public = {topic.pk for topic in form.cleaned_data["public_topics"]}
        set_profile_interest_visibility(
            profile=self.request.user, public_topic_ids=public,
        )
        _sync_existing_public_audiences(
            profile=self.request.user,
            kind=ProfileVisibilityTargetKind.INTEREST,
            rows=ProfileInterest.objects.filter(profile=self.request.user),
            published=public,
        )
        messages.success(self.request, "Centres d’intérêt mis à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("account:interests")


class ProfileOpenToSettingsView(LoginRequiredMixin, FormView):
    login_url = "core:login"
    template_name = "topics/open_to.html"
    form_class = OpenToSettingsForm

    def get_initial(self):
        initial = super().get_initial()
        rows = ProfileOpenTo.objects.filter(profile=self.request.user, is_active=True, topic__isnull=True)
        initial["kinds"] = list(rows.values_list("kind", flat=True))
        visibility = ProfileVisibilityResolver(owner=self.request.user)
        initial["public_kinds"] = [
            row.kind for row in rows if visibility.open_to(row)
        ]
        initial["searchable_kinds"] = list(rows.filter(is_searchable=True).values_list("kind", flat=True))
        return initial

    @transaction.atomic
    def form_valid(self, form):
        kinds = set(form.cleaned_data["kinds"])
        # Respect explicit public checkboxes at creation, not only edits.
        # Defaults are proposed by the form, never imposed after submission.
        public = set(form.cleaned_data["public_kinds"])
        replace_profile_open_to(
            profile=self.request.user, kinds=kinds, public_kinds=public,
            searchable_kinds=form.cleaned_data["searchable_kinds"],
        )
        _sync_existing_public_audiences(
            profile=self.request.user,
            kind=ProfileVisibilityTargetKind.OPEN_TO,
            rows=ProfileOpenTo.objects.filter(
                profile=self.request.user, is_active=True, topic__isnull=True,
            ),
            published=public,
        )
        messages.success(self.request, "Préférences Ouvert à mises à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("account:open-to")
