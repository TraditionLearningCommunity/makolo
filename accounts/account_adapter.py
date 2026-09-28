from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class MakoloAccountAdapter(DefaultAccountAdapter):
    """Route a social account through Makolo identifier setup before the shell."""

    def get_login_redirect_url(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not getattr(user, "username_configured", True):
            return reverse("account:identifier-setup")
        return super().get_login_redirect_url(request)
