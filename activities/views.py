from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization, SpaceArchetype
from subscriptions.ux_continuation import action_subscription_handoff, is_subscription_denial

from .forms import ActivityCreateForm
from .models import ActivityStatus
from .services import create_activity


class ActivityCreateView(LoginRequiredMixin, FormView):
    template_name = "activities/activity_form.html"
    form_class = ActivityCreateForm
    login_url = "core:login"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def _context_space(self):
        """Contextual creation is a suggestion, never a Mandate."""
        slug = (self.request.GET.get("space") or "").strip()
        if not slug:
            return None
        space = Organization.objects.filter(slug=slug).first()
        if space is None or not can(
            self.request.user, PermissionCode.SPACE_ACTIVITIES_MANAGE, space
        ):
            return None
        if space.archetype not in {
            SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
            SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA,
        }:
            return None
        return space

    def get_initial(self):
        initial = super().get_initial()
        space = self._context_space()
        if space is not None:
            initial["organization"] = space.pk
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        space = self._context_space()
        if space is not None:
            context["create_space_context"] = space
            context["create_space_label"] = (
                "Nouvelle initiative"
                if space.archetype == SpaceArchetype.COMMUNITY
                else "Nouvelle création"
                if space.archetype == SpaceArchetype.CREATIVE
                else "Nouvelle production"
                if space.archetype == SpaceArchetype.MEDIA
                else "Nouvelle activité"
            )
            context["create_space_return"] = True
        if getattr(self, "_subscription_handoff", None):
            context["subscription_handoff"] = self._subscription_handoff
        return context

    def post(self, request, *args, **kwargs):
        # Reject a forged Space context before form validation turns it into a
        # generic invalid choice. The submitted identifier is never trusted as
        # proof of authority.
        raw_space_id = (request.POST.get("organization") or "").strip()
        if raw_space_id:
            space = get_object_or_404(Organization, pk=raw_space_id)
            if not can(request.user, PermissionCode.SPACE_ACTIVITIES_MANAGE, space):
                raise PermissionDenied("Vous ne pouvez pas organiser une Activity au nom de cet Espace.")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        space = form.cleaned_data.get("organization")
        if space is not None and not can(
            self.request.user,
            PermissionCode.SPACE_ACTIVITIES_MANAGE,
            space,
        ):
            raise PermissionDenied("Vous ne pouvez pas organiser une Activity au nom de cet Espace.")
        try:
            activity = create_activity(
                space=space,
                owner_profile=self.request.user if space is None else None,
                created_by=self.request.user,
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data["short_description"],
                description=form.cleaned_data["description"],
                visibility=form.cleaned_data["visibility"],
                status=ActivityStatus.DRAFT,
            )
        except ValidationError as exc:
            if is_subscription_denial(exc):
                # Only a confirmed Subscription gate, not any field error,
                # produces a scoped continuation handoff.
                from django.urls import reverse
                from urllib.parse import urlencode
                action_url = reverse("activities:create")
                if space is not None:
                    action_url += "?" + urlencode({"space": space.slug})
                self._subscription_handoff = action_subscription_handoff(
                    self.request, space=space, action_url=action_url,
                )
            form.add_error(None, "; ".join(exc.messages if hasattr(exc, "messages") else [str(exc)]))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Activité « {activity.title} » créée en brouillon.",
        )
        context_space = self._context_space()
        if context_space is not None and space == context_space:
            return redirect("organizations:space-work", slug=context_space.slug)
        return redirect("core:participant-home")
