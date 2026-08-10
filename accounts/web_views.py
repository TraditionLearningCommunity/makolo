from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from .forms import (
    AccountDeleteForm,
    AccountProfileForm,
    AccountRegistrationForm,
    NotificationPreferencesForm,
    PasswordForgotForm,
    PasswordResetWebForm,
)
from .models import NotificationPreference, UserProfile
from .services import (
    delete_account,
    get_account_deletion_blockers,
    request_password_reset,
    reset_password,
)


class AccountRegistrationView(FormView):
    template_name = "accounts/register.html"
    form_class = AccountRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Compte créé. Vous pouvez maintenant vous connecter.")
        return redirect("core:login")


class PasswordForgotView(FormView):
    template_name = "accounts/password_forgot.html"
    form_class = PasswordForgotForm

    def form_valid(self, form):
        request_password_reset(email=form.cleaned_data["email"])
        return render(self.request, "accounts/password_forgot_done.html")


class PasswordResetConfirmView(FormView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = PasswordResetWebForm

    def form_valid(self, form):
        try:
            reset_password(
                uid=self.kwargs["uid"],
                token=self.kwargs["token"],
                new_password=form.cleaned_data["new_password"],
            )
        except ValidationError as exc:
            message_dict = getattr(exc, "message_dict", {})
            messages_list = message_dict.get("token") or exc.messages
            for message in messages_list:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, "Mot de passe réinitialisé. Connectez-vous avec votre nouveau mot de passe.")
        return redirect("core:login")


class AccountProfileView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "accounts/profile.html"

    def _objects(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return profile, preferences

    def _context(self, request, profile_form, preferences_form):
        return {
            "profile_form": profile_form,
            "preferences_form": preferences_form,
            "deletion_blockers": get_account_deletion_blockers(request.user),
        }

    def get(self, request):
        profile, preferences = self._objects(request)
        return render(
            request,
            self.template_name,
            self._context(
                request,
                AccountProfileForm(instance=request.user, profile=profile),
                NotificationPreferencesForm(instance=preferences),
            ),
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
            self._context(request, profile_form, preferences_form),
            status=400,
        )


class AccountPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    login_url = "core:login"
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("account:profile")

    def form_valid(self, form):
        messages.success(self.request, "Mot de passe modifié avec succès.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, FormView):
    login_url = "core:login"
    template_name = "accounts/delete_account.html"
    form_class = AccountDeleteForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["deletion_blockers"] = get_account_deletion_blockers(self.request.user)
        return context

    def form_valid(self, form):
        try:
            delete_account(
                user=self.request.user,
                current_password=form.cleaned_data["password"],
            )
        except ValidationError as exc:
            message_dict = getattr(exc, "message_dict", {})
            password_messages = message_dict.get("password", [])
            account_messages = message_dict.get("account", [])
            for message in password_messages:
                form.add_error("password", message)
            for message in account_messages:
                form.add_error(None, message)
            if not password_messages and not account_messages:
                for message in exc.messages:
                    form.add_error(None, message)
            return self.form_invalid(form)

        logout(self.request)
        messages.success(self.request, "Votre compte Makolo a été désactivé et anonymisé.")
        return redirect("core:home")
