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
        replace_profile_interests(profile=self.request.user, topic_ids=[topic.pk for topic in form.cleaned_data["topics"]])
        set_profile_interest_visibility(profile=self.request.user, public_topic_ids=[topic.pk for topic in form.cleaned_data["public_topics"]])
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
        replace_profile_open_to(profile=self.request.user, kinds=form.cleaned_data["kinds"], public_kinds=form.cleaned_data["public_kinds"], searchable_kinds=form.cleaned_data["searchable_kinds"])
        messages.success(self.request, "Préférences Ouvert à mises à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("account:open-to")
