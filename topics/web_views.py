from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import FormView

from .forms import InterestSelectionForm, OpenToSettingsForm
from .models import ProfileInterest, ProfileOpenTo
from .services import replace_profile_interests, replace_profile_open_to, set_profile_interest_visibility


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
        initial["public_topics"] = list(rows.filter(is_public=True).values_list("topic_id", flat=True))
        return initial

    def form_valid(self, form):
        # A newly selected Interest is public by default; the legacy form's
        # public_topics picker lists only already saved Interests. Preserve
        # explicit visibility choices for all retained rows.
        existing = set(ProfileInterest.objects.filter(
            profile=self.request.user,
        ).values_list("topic_id", flat=True))
        selected = {topic.pk for topic in form.cleaned_data["topics"]}
        replace_profile_interests(profile=self.request.user, topic_ids=selected)
        public = {topic.pk for topic in form.cleaned_data["public_topics"]}
        public.update(selected - existing)
        set_profile_interest_visibility(
            profile=self.request.user, public_topic_ids=public,
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
        initial["public_kinds"] = list(rows.filter(is_public=True).values_list("kind", flat=True))
        initial["searchable_kinds"] = list(rows.filter(is_searchable=True).values_list("kind", flat=True))
        return initial

    def form_valid(self, form):
        retained = set(ProfileOpenTo.objects.filter(
            profile=self.request.user, is_active=True, topic__isnull=True,
        ).values_list("kind", flat=True))
        kinds = set(form.cleaned_data["kinds"])
        public = set(form.cleaned_data["public_kinds"])
        public.update(kinds - retained)
        replace_profile_open_to(
            profile=self.request.user, kinds=kinds, public_kinds=public,
            searchable_kinds=form.cleaned_data["searchable_kinds"],
        )
        messages.success(self.request, "Préférences Ouvert à mises à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("account:open-to")
