"""Private, owner-authorized multimodal reception for Makolo Mark.

A receipt only confirms intake into sharing.InboundCapture. It does not
execute the request or transfer any Permission, Access or Proof.
"""
import json

from django.core.exceptions import ValidationError as DomainValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from core.api.me_views import PersonalProjectionAPIView
from core.api.projections import projection_envelope
from organizations.api.workspace_projection import workspace_spaces
from sharing.inbound_bundle_services import bundle_receipt, receive_inbound_bundle
from sharing.inbound_models import InboundCaptureBundle


class MarkIntakeThrottle(UserRateThrottle):
    rate = "30/hour"


def _decode_json(value, expected, field):
    if value is None or value == "":
        return expected()
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError) as exc:
        raise ValidationError({field: ["Valeur invalide."]}) from exc
    if not isinstance(decoded, expected):
        raise ValidationError({field: ["Format invalide."]})
    return decoded


def _receive(request, *, space, projection):
    permitted = {"request_key", "text", "links", "context", "files"}
    unexpected = set(request.data.keys()) - permitted
    if unexpected:
        raise ValidationError({"request": ["Paramètres non autorisés."]})
    links = _decode_json(request.data.get("links"), list, "links")
    context = _decode_json(request.data.get("context"), dict, "context")
    files = request.FILES.getlist("files")
    try:
        receipt, created = receive_inbound_bundle(
            actor=request.user, space=space,
            request_key=str(request.data.get("request_key") or ""),
            text=request.data.get("text", ""),
            links=links, context=context, files=files,
        )
    except DomainValidationError as exc:
        raise ValidationError({"request": exc.messages}) from exc
    observed_at = timezone.now()
    result = Response(
        projection_envelope(
            projection=projection,
            data=bundle_receipt(receipt),
            generated_at=observed_at,
            **({"scope": "space"} if space is not None else {}),
        ),
        status=201 if created else 200,
    )
    result["Cache-Control"] = "private, no-store"
    result["X-Content-Type-Options"] = "nosniff"
    return result


def _receipt(request, *, space, receipt_id, projection):
    receipt = InboundCaptureBundle.objects.filter(
        pk=receipt_id, created_by=request.user, space=space,
    ).select_related("space").first()
    if receipt is None:
        raise NotFound()
    result = Response(projection_envelope(
        projection=projection, data=bundle_receipt(receipt),
        generated_at=timezone.now(),
        **({"scope": "space"} if space is not None else {}),
    ))
    result["Cache-Control"] = "private, no-store"
    result["X-Content-Type-Options"] = "nosniff"
    return result


class PersonalMarkIntakeAPIView(PersonalProjectionAPIView):
    projection_code = "personal.mark.intake"
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        self._guard_personal_scope(request)
        key = str(request.query_params.get("request_key") or "")
        if not key or len(key) > 64:
            raise ValidationError({"request_key": "Identifiant requis."})
        bundle = InboundCaptureBundle.objects.filter(
            created_by=request.user, space__isnull=True, request_key=key,
        ).first()
        if bundle is None:
            raise NotFound()
        return _receipt(
            request, space=None, receipt_id=bundle.pk,
            projection=self.projection_code,
        )


    def get_throttles(self):
        checks = super().get_throttles()
        if self.request.method == "POST":
            checks.append(MarkIntakeThrottle())
        return checks

    def post(self, request):
        self._guard_personal_scope(request, include_body=True)
        return _receive(request, space=None, projection=self.projection_code)


class PersonalMarkReceiptAPIView(PersonalProjectionAPIView):
    projection_code = "personal.mark.intake"

    def get(self, request, receipt_id):
        self._guard_personal_scope(request)
        return _receipt(
            request, space=None, receipt_id=receipt_id,
            projection=self.projection_code,
        )


class SpaceMarkIntakeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, slug):
        space = self._space(request, slug)
        key = str(request.query_params.get("request_key") or "")
        if not key or len(key) > 64:
            raise ValidationError({"request_key": "Identifiant requis."})
        bundle = InboundCaptureBundle.objects.filter(
            created_by=request.user, space=space, request_key=key,
        ).first()
        if bundle is None:
            raise NotFound()
        return _receipt(
            request, space=space, receipt_id=bundle.pk,
            projection="space.mark.intake",
        )


    def get_throttles(self):
        checks = super().get_throttles()
        if self.request.method == "POST":
            checks.append(MarkIntakeThrottle())
        return checks

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        if not has_direct_space_permission(request.user, space, PermissionCode.SPACE_MANAGE):
            raise PermissionDenied("Vous ne pouvez pas transmettre une demande pour cet Espace.")
        return space

    def post(self, request, slug):
        space = self._space(request, slug)
        return _receive(request, space=space, projection="space.mark.intake")


class SpaceMarkReceiptAPIView(SpaceMarkIntakeAPIView):
    def get(self, request, slug, receipt_id):
        space = self._space(request, slug)
        return _receipt(
            request, space=space, receipt_id=receipt_id,
            projection="space.mark.intake",
        )
