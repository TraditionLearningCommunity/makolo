from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from accounts.models import PermissionGroup, Role


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "base/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()

        context.update(
            {
                "users_count": User.objects.count(),
                "verified_users_count": User.objects.filter(
                    is_verified=True
                ).count(),
                "roles_count": Role.objects.filter(is_active=True).count(),
                "permission_groups_count": PermissionGroup.objects.count(),
            }
        )
        return context
