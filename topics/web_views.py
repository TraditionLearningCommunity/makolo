from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import FormView

from .forms import InterestSelectionForm
from .models import ProfileInterest
from .services import replace_profile_interests


class ProfileInterestSettingsView(LoginRequiredMixin, FormView):
    login_url = "core:login"
    template_name = "topics/interests.html"
    form_class = InterestSelectionForm

    def get_initial(self):
        initial = super().get_initial()
        initial["topics"] = list(
            ProfileInterest.objects.filter(profile=self.request.user).values_list("topic_id", flat=True)
        )
        return initial

    def form_valid(self, form):
        replace_profile_interests(
            profile=self.request.user,
            topic_ids=[topic.pk for topic in form.cleaned_data["topics"]],
        )
        messages.success(self.request, "Centres d’intérêt mis à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("account:interests")
