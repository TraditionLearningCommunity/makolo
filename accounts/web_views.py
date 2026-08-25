from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, TemplateView

from core.web_throttling import (
    RATE_LIMIT_MESSAGE,
    allow_web_request,
    client_rate_identity,
    value_rate_identity,
)

from .device_accounts import (
    forget_account_on_device,
    remembered_accounts_for_request,
    remembered_device_for_user,
)
from .forms import (
    AccountDeleteForm,
    AccountProfileForm,
    AccountRegistrationForm,
    AppearancePreferencesForm,
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


def _rate_limited_form_response(view):
    form = view.get_form()
    form.add_error(None, RATE_LIMIT_MESSAGE)
    response = view.form_invalid(form)
    response.status_code = 429
    return response


def _safe_next_url(request, value):
    value = (value or "").strip()
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return ""


class AccountRegistrationView(FormView):
    template_name = "accounts/register.html"
    form_class = AccountRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            next_url = _safe_next_url(request, request.GET.get("next"))
            return redirect(next_url or "core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_url"] = _safe_next_url(
            self.request,
            self.request.POST.get("next") or self.request.GET.get("next"),
        )
        return context

    def post(self, request, *args, **kwargs):
        if not allow_web_request(
            request,
            scope="registration",
            limit=5,
            window_seconds=3600,
            identities=[client_rate_identity(request)],
        ):
            return _rate_limited_form_response(self)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Compte créé. Vous pouvez maintenant vous connecter.")
        next_url = _safe_next_url(self.request, self.request.POST.get("next"))
        login_url = reverse("core:login")
        query = {"email": form.cleaned_data["email"]}
        if next_url:
            query["next"] = next_url
        return redirect(f"{login_url}?{urlencode(query)}")


class PasswordForgotView(FormView):
    template_name = "accounts/password_forgot.html"
    form_class = PasswordForgotForm

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email", "")
        if not allow_web_request(
            request,
            scope="password-forgot",
            limit=5,
            window_seconds=3600,
            identities=[
                client_rate_identity(request),
                value_rate_identity("email", email),
            ],
        ):
            return _rate_limited_form_response(self)
        return super().post(request, *args, **kwargs)

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

    def _context(
        self,
        request,
        profile,
        profile_form,
        preferences_form,
        appearance_form=None,
    ):
        if appearance_form is None:
            appearance_form = AppearancePreferencesForm(profile=profile)
        return {
            "profile_form": profile_form,
            "preferences_form": preferences_form,
            "appearance_form": appearance_form,
            "deletion_blockers": get_account_deletion_blockers(request.user),
        }

    def get(self, request):
        profile, preferences = self._objects(request)
        return render(
            request,
            self.template_name,
            self._context(
                request,
                profile,
                AccountProfileForm(instance=request.user, profile=profile),
                NotificationPreferencesForm(instance=preferences),
            ),
        )

    def post(self, request):
        profile, preferences = self._objects(request)
        section = request.POST.get("section", "profile")
        appearance_form = None

        if section == "appearance":
            appearance_form = AppearancePreferencesForm(request.POST, profile=profile)
            profile_form = AccountProfileForm(instance=request.user, profile=profile)
            preferences_form = NotificationPreferencesForm(instance=preferences)
            if appearance_form.is_valid():
                appearance_form.save()
                messages.success(request, "Apparence mise à jour.")
                return redirect(f"{reverse('account:profile')}#appearance")
        elif section == "notifications":
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
            self._context(
                request,
                profile,
                profile_form,
                preferences_form,
                appearance_form,
            ),
            status=400,
        )


class AccountPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    login_url = "core:login"
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("account:profile")

    def form_valid(self, form):
        messages.success(self.request, "Mot de passe modifié avec succès.")
        return super().form_valid(form)


class AccountSwitcherView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "accounts/account_switcher.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        devices = remembered_accounts_for_request(self.request)
        context["remembered_accounts"] = [row.user for row in devices]
        return context


class SwitchRememberedAccountView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, user_id):
        device = remembered_device_for_user(request, user_id)
        if device is None:
            raise Http404("Ce compte n'est pas mémorisé sur cet appareil.")
        if device.user_id == request.user.pk:
            return redirect("core:participant-home")
        target_email = device.user.email
        logout(request)
        login_url = reverse("core:login")
        query = urlencode({"email": target_email, "next": reverse("core:participant-home")})
        return redirect(f"{login_url}?{query}")


class AddAccountView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request):
        logout(request)
        login_url = reverse("core:login")
        query = urlencode({"next": reverse("core:participant-home")})
        return redirect(f"{login_url}?{query}")


class RemoveRememberedAccountView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, user_id):
        if not forget_account_on_device(request, user_id):
            raise Http404("Ce compte n'est pas mémorisé sur cet appareil.")
        messages.success(request, "Compte retiré de cet appareil.")
        return redirect("account:switcher")


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
