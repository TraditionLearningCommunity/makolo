from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .forms import AccountProfileForm, NotificationPreferencesForm
from .models import NotificationPreference, UserProfile


class AccountProfileView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "accounts/profile.html"

    def _objects(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return profile, preferences

    def get(self, request):
        profile, preferences = self._objects(request)
        return render(
            request,
            self.template_name,
            {
                "profile_form": AccountProfileForm(instance=request.user, profile=profile),
                "preferences_form": NotificationPreferencesForm(instance=preferences),
            },
        )

    def post(self, request):
        profile, preferences = self._objects(request)
        section = request.POST.get("section", "profile")

        if section == "notifications":
            preferences_form = NotificationPreferencesForm(request.POST, instance=preferences)
            profile_form = AccountProfileForm(instance=request.user, profile=profile)
            if preferences_form.is_valid():
                preferences_form.save()
                messages.success(request, "Préférences de notification mises à jour.")
                return redirect("account:profile")
        else:
            profile_form = AccountProfileForm(
                request.POST,
                request.FILES,
                instance=request.user,
                profile=profile,
            )
            preferences_form = NotificationPreferencesForm(instance=preferences)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profil mis à jour.")
                return redirect("account:profile")

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "preferences_form": preferences_form,
            },
            status=400,
        )


class AccountPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    login_url = "core:login"
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("account:profile")

    def form_valid(self, form):
        messages.success(self.request, "Mot de passe modifié avec succès.")
        return super().form_valid(form)
