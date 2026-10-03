from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import RedirectView


User = get_user_model()


class PublicProfileView(RedirectView):
    """Compatibility entry point redirecting to the canonical public Passeport."""

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        user = get_object_or_404(
            User.objects.filter(
                is_active=True,
                profile__public_profile=True,
                profile__searchable=True,
            ),
            pk=self.kwargs["profile_id"],
        )
        return reverse("public-passport", kwargs={"identifier": user.username})
