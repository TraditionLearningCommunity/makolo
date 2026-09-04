from django.contrib.auth import get_user_model
from django.http import Http404
from django.views.generic import DetailView

from activities.models import Activity, ActivityStatus, ActivityVisibility
from topics.services import public_profile_interests, public_profile_open_to

from .models import UserProfile


User = get_user_model()


class PublicProfileView(DetailView):
    """Stable privacy-safe projection of a Profile; searchable is intentionally irrelevant here."""

    model = User
    template_name = "accounts/public_profile.html"
    context_object_name = "profile_user"
    pk_url_kwarg = "profile_id"

    def get_queryset(self):
        return User.objects.filter(is_active=True, profile__public_profile=True).select_related("profile")

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            raise Http404("Ce profil public n’est pas disponible.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        context["public_interests"] = public_profile_interests(profile=user)
        context["open_to"] = public_profile_open_to(profile=user)
        context["public_activities"] = Activity.objects.filter(
            owner_profile=user,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        ).order_by("title", "id")
        context["declared_links"] = [
            (label, value) for label, value in (
                ("Site web", user.website), ("LinkedIn", user.linkedin_url),
                ("Facebook", user.facebook_url), ("Instagram", user.instagram_url),
                ("TikTok", user.tiktok_url), ("X / Twitter", user.x_url), ("YouTube", user.youtube_url),
            ) if value
        ]
        return context
