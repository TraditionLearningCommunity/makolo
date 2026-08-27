from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from .models import ProfileFollow
from .profile_follow_services import follow_profile, unfollow_profile


User = get_user_model()


class ProfileFollowingListView(LoginRequiredMixin, ListView):
    model = ProfileFollow
    template_name = "organizations/profile_following_list.html"
    context_object_name = "follows"
    paginate_by = 30

    def get_queryset(self):
        return ProfileFollow.objects.filter(user=self.request.user).select_related(
            "organizer_profile",
            "organizer_profile__profile",
        )


class ProfileFollowView(LoginRequiredMixin, View):
    template_name = "organizations/profile_follow.html"

    def _organizer(self, request, profile_id):
        return get_object_or_404(
            User.objects.select_related("profile").exclude(pk=request.user.pk),
            pk=profile_id,
            profile__public_profile=True,
            profile__searchable=True,
            is_active=True,
        )

    def get(self, request, profile_id):
        organizer = self._organizer(request, profile_id)
        follow = ProfileFollow.objects.filter(
            organizer_profile=organizer,
            user=request.user,
        ).first()
        return render(
            request,
            self.template_name,
            {"organizer": organizer, "follow": follow},
        )

    def post(self, request, profile_id):
        organizer = self._organizer(request, profile_id)
        follow = ProfileFollow.objects.filter(
            organizer_profile=organizer,
            user=request.user,
        ).first()
        if follow:
            unfollow_profile(follow=follow, user=request.user)
            messages.success(request, "Vous ne suivez plus cet organisateur.")
        else:
            follow_profile(user=request.user, organizer_profile=organizer)
            messages.success(request, "Vous suivez maintenant cet organisateur.")
        fallback = reverse(
            "organizer_public:profile-follow",
            kwargs={"profile_id": organizer.pk},
        )
        next_url = (request.POST.get("next") or "").strip()
        if not next_url or not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = fallback
        return redirect(next_url)
