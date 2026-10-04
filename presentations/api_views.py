from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from access.selectors import access_credential_is_presentable_to
from activities.models import Activity, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from core.api.me_views import PersonalProjectionAPIView
from core.api.projections import projection_envelope
from core.participant_selectors import participant_accesses_visible_to_buyer
from core.product_language import vocabulary_for

from .contexts import build_access_context, build_activity_context
from .enums import PresentationPurpose
from .mobile_projection import (
    MPS_ARTIFACT_PROJECTION,
    MPS_TEMPLATE_PROJECTION,
    MPS_THEME_PROJECTION,
    artifact_payload,
    template_definition_payload,
    theme_definition_payload,
)
from .product_usage import access_presentation_purpose
from .resolver import resolve_presentation


MOBILE_ACTIVITY_PURPOSES = {
    PresentationPurpose.PUBLIC_PAGE,
    PresentationPurpose.INVITATION,
    PresentationPurpose.PROGRAM,
}


def _activity_queryset():
    return Activity.objects.select_related("space", "owner_profile").prefetch_related(
        "occurrences__place_links__place"
    )


def _access_queryset(profile):
    return (
        participant_accesses_visible_to_buyer(profile)
        .select_related(
            "activity",
            "activity__space",
            "activity__owner_profile",
            "occurrence",
            "journey",
        )
        .prefetch_related("occurrence__place_links__place")
    )


def _occurrence(activity):
    return activity.occurrences.order_by("start_at", "id").first()


def _activity_visible_to(profile, activity):
    return activity.visibility == ActivityVisibility.PUBLIC or can(
        profile,
        PermissionCode.ACTIVITY_MANAGE,
        activity=activity,
    )


def _artifact_response(data, *, observed_at, scope="personal"):
    response = Response(
        projection_envelope(
            projection=MPS_ARTIFACT_PROJECTION,
            data=data,
            generated_at=observed_at,
            scope=scope,
        )
    )
    response["Cache-Control"] = "private, no-store"
    return response


def _definition_response(*, projection, data, observed_at):
    response = Response(
        projection_envelope(
            projection=projection,
            data=data,
            generated_at=observed_at,
        )
    )
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


class PersonalAccessPresentationAPIView(PersonalProjectionAPIView):
    projection_code = MPS_ARTIFACT_PROJECTION

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        access = get_object_or_404(_access_queryset(request.user), pk=pk)
        purpose = access_presentation_purpose(access)
        resolved = resolve_presentation(
            activity=access.activity,
            occurrence=access.occurrence,
            purpose=purpose,
        )
        vocabulary = vocabulary_for(
            activity=access.activity,
            workflow=getattr(access.journey, "workflow", None),
        )
        context = build_access_context(
            access=access,
            editorial=resolved.binding.editorial_data if resolved.binding else {},
            display_type=vocabulary.access_noun,
            include_qr=False,
        )
        capabilities = []
        links = {}
        if access_credential_is_presentable_to(
            request.user,
            access,
            at=observed_at,
        ):
            capabilities.append("open_credential")
            links["credential"] = f"/api/v1/me/accesses/{access.pk}/credential/"

        return _artifact_response(
            artifact_payload(
                subject_kind="access",
                subject_id=access.pk,
                purpose=purpose,
                resolved=resolved,
                context=context,
                template_link_name="presentations-api:access-template",
                theme_link_name="presentations-api:access-theme",
                link_kwargs={"pk": access.pk},
                capabilities=capabilities,
                links=links,
            ),
            observed_at=observed_at,
        )


class _AccessDefinitionMixin:
    def _resolved(self, request, pk):
        access = get_object_or_404(_access_queryset(request.user), pk=pk)
        resolved = resolve_presentation(
            activity=access.activity,
            occurrence=access.occurrence,
            purpose=access_presentation_purpose(access),
        )
        return resolved


class PersonalAccessTemplateAPIView(_AccessDefinitionMixin, PersonalProjectionAPIView):
    projection_code = MPS_TEMPLATE_PROJECTION

    def get(self, request, pk, version_id):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        resolved = self._resolved(request, pk)
        version = resolved.template_version
        if version is None or version.pk != version_id:
            raise Http404
        return _definition_response(
            projection=MPS_TEMPLATE_PROJECTION,
            data=template_definition_payload(version),
            observed_at=observed_at,
        )


class PersonalAccessThemeAPIView(_AccessDefinitionMixin, PersonalProjectionAPIView):
    projection_code = MPS_THEME_PROJECTION

    def get(self, request, pk, version_id):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        resolved = self._resolved(request, pk)
        version = resolved.theme_version
        if version is None or version.pk != version_id:
            raise Http404
        return _definition_response(
            projection=MPS_THEME_PROJECTION,
            data=theme_definition_payload(version),
            observed_at=observed_at,
        )


class ActivityPresentationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, purpose):
        if purpose not in MOBILE_ACTIVITY_PURPOSES:
            raise Http404
        activity = get_object_or_404(_activity_queryset(), pk=pk)
        if not _activity_visible_to(request.user, activity):
            raise Http404
        observed_at = timezone.now()
        resolved = resolve_presentation(
            activity=activity,
            occurrence=_occurrence(activity),
            purpose=purpose,
        )
        context = build_activity_context(
            activity=activity,
            occurrence=_occurrence(activity),
            editorial=resolved.binding.editorial_data if resolved.binding else {},
        )
        return _artifact_response(
            artifact_payload(
                subject_kind="activity",
                subject_id=activity.pk,
                purpose=purpose,
                resolved=resolved,
                context=context,
                template_link_name="presentations-api:activity-template",
                theme_link_name="presentations-api:activity-theme",
                link_kwargs={"pk": activity.pk, "purpose": purpose},
            ),
            observed_at=observed_at,
            scope="activity",
        )


class _ActivityDefinitionMixin:
    def _resolved(self, request, pk, purpose):
        if purpose not in MOBILE_ACTIVITY_PURPOSES:
            raise Http404
        activity = get_object_or_404(_activity_queryset(), pk=pk)
        if not _activity_visible_to(request.user, activity):
            raise Http404
        return resolve_presentation(
            activity=activity,
            occurrence=_occurrence(activity),
            purpose=purpose,
        )


class ActivityTemplateAPIView(_ActivityDefinitionMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, purpose, version_id):
        observed_at = timezone.now()
        resolved = self._resolved(request, pk, purpose)
        version = resolved.template_version
        if version is None or version.pk != version_id:
            raise Http404
        return _definition_response(
            projection=MPS_TEMPLATE_PROJECTION,
            data=template_definition_payload(version),
            observed_at=observed_at,
        )


class ActivityThemeAPIView(_ActivityDefinitionMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, purpose, version_id):
        observed_at = timezone.now()
        resolved = self._resolved(request, pk, purpose)
        version = resolved.theme_version
        if version is None or version.pk != version_id:
            raise Http404
        return _definition_response(
            projection=MPS_THEME_PROJECTION,
            data=theme_definition_payload(version),
            observed_at=observed_at,
        )
