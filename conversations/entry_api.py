from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, views
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
import hashlib

from core.api.privacy import PrivateNoStoreMixin
from organizations.models import Organization
from .entry_services import (ExchangeConflict, acknowledge_entries, delete_entry, edit_entry,
                             entries_for, lock_point, react_entry, send_entry)
from .entry_projection import entry_ack, project_entry, projected_rows
from .point_models import ConversationPoint, PointExchangeEntry
from .point_services import point_visible_to
from .rich_services import readable_exchange_entries
from .profile_scope import ConversationProfileScopeMixin


class EntryThrottle(UserRateThrottle):
    rate = "120/min"
    scope = "conversation-entry"


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError("Champs d'envoi invalides.")
        return super().to_internal_value(data)


class SendSerializer(StrictSerializer):
    body = serializers.CharField(max_length=5000, allow_blank=True)
    client_reference = serializers.CharField(max_length=80)
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    represented_space_id = serializers.UUIDField(required=False, allow_null=True)
    mention_profile_ids = serializers.ListField(child=serializers.UUIDField(), max_length=20, required=False, default=list)
    references = serializers.ListField(child=serializers.DictField(), max_length=10, required=False, default=list)


class EditSerializer(StrictSerializer):
    body = serializers.CharField(max_length=5000, allow_blank=True)
    expected_edit_version = serializers.IntegerField(min_value=1)
    client_reference = serializers.CharField(max_length=80)
    mention_profile_ids = serializers.ListField(child=serializers.UUIDField(), max_length=20, required=False)


class ReactionSerializer(StrictSerializer):
    emoji = serializers.CharField(max_length=16)
    selected = serializers.BooleanField()
    client_reference = serializers.CharField(max_length=80, required=False)


class ReceiptSerializer(StrictSerializer):
    delivered_sequence = serializers.IntegerField(min_value=0)
    read_sequence = serializers.IntegerField(min_value=0, default=0)


def validate(serializer, request):
    value = serializer(data=request.data)
    value.is_valid(raise_exception=True)
    return value.validated_data


def point_for(profile, pk):
    point = get_object_or_404(ConversationPoint.objects.select_related("conversation__policy"), pk=pk, kind="exchange")
    if not point_visible_to(profile, point):
        raise NotFound("Échange inaccessible.")
    return point


def entry_for(profile, pk):
    entry = get_object_or_404(PointExchangeEntry, pk=pk)
    point = point_for(profile, entry.point_id)
    return get_object_or_404(entries_for(profile, point), pk=pk)


def integer(request, key, default=0, maximum=2**63-1):
    try:
        value = int(request.query_params.get(key, default))
        if not 0 <= value <= maximum:
            raise ValueError
        return value
    except (ValueError, TypeError) as exc:
        raise serializers.ValidationError({key: "Entier positif attendu."}) from exc


def projection_scope(point, profile):
    from .services import can_manage_conversation
    value = f"{point.pk}:{profile.pk}:{point.response_visibility}:{point.conversation.history_policy}:{can_manage_conversation(profile, point.conversation)}"
    return hashlib.sha256(value.encode()).hexdigest()


class EntryAPIView(ConversationProfileScopeMixin, PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [EntryThrottle]

    def handle_exception(self, exc):
        if isinstance(exc, ExchangeConflict):
            return Response({"errors": exc.messages}, status=409)
        if isinstance(exc, ValidationError):
            return Response({"errors": getattr(exc, "message_dict", exc.messages)}, status=400)
        return super().handle_exception(exc)


class ConversationExchangeEntriesAPIView(EntryAPIView):
    def post(self, request, point_pk):
        point = point_for(request.user, point_pk)
        data = validate(SendSerializer, request)
        reply_id, space_id = data.pop("reply_to_id", None), data.pop("represented_space_id", None)
        reply = get_object_or_404(entries_for(request.user, point), pk=reply_id) if reply_id else None
        space = get_object_or_404(Organization, pk=space_id) if space_id else None
        entry = send_entry(actor=request.user, point=point, reply_to=reply, represented_space=space, **data)
        return Response({**entry_ack(entry, profile=request.user), "entry": project_entry(request.user, entry)})

    def get(self, request, point_pk):
        point = point_for(request.user, point_pk)
        limit = max(1, integer(request, "limit", 25, 50))
        before = integer(request, "before_sequence")
        cursor = None
        if before or request.query_params.get("order") == "latest":
            rows = entries_for(request.user, point)
            if before:
                rows = rows.filter(sequence__lt=before)
            page = list(projected_rows(rows).order_by("-sequence")[:limit+1])
            more = len(page) > limit
            page = list(reversed(page[:limit]))
        else:
            page, cursor = readable_exchange_entries(request.user, point, cursor=request.query_params.get("cursor"), limit=limit)
            more = cursor is not None
        return Response({"viewer_profile_id": str(request.user.pk), "scope": projection_scope(point, request.user), "results": [project_entry(request.user, row, point=point) for row in page],
                         "next_cursor": cursor, "has_more": more,
                         "before_sequence": page[0].sequence if more and page else None,
                         "stream_version": point.exchange_stream_version})


class ConversationEntrySyncAPIView(EntryAPIView):
    @transaction.atomic
    def get(self, request, point_pk):
        # All writers lock this Point. Projection and watermark form one snapshot.
        point_for(request.user, point_pk)
        point = lock_point(point_pk)
        after = integer(request, "after_version")
        if after > point.exchange_stream_version:
            return Response({"detail": "Synchronisation à reprendre.", "reset_required": True}, status=409)
        limit = max(1, integer(request, "limit", 50, 50))
        rows = entries_for(request.user, point).filter(last_change_version__gt=after)
        page = list(projected_rows(rows).order_by("last_change_version", "pk")[:limit+1])
        more = len(page) > limit
        page = page[:limit]
        return Response({"viewer_profile_id": str(request.user.pk), "point_id": str(point.pk), "scope": projection_scope(point, request.user), "stream_version": point.exchange_stream_version,
                         "results": [project_entry(request.user, row, point=point) for row in page],
                         "next_version": page[-1].last_change_version if more else point.exchange_stream_version,
                         "has_more": more})


class ConversationEntryDetailAPIView(EntryAPIView):
    @transaction.atomic
    def get(self, request, entry_pk):
        target = entry_for(request.user, entry_pk)
        point = lock_point(target.point_id)
        rows = entries_for(request.user, point)
        # Recheck after the Point lock; never fetch surrounding history first.
        target = get_object_or_404(rows, pk=entry_pk)
        older = list(projected_rows(rows.filter(sequence__lt=target.sequence)).order_by("-sequence")[:25])
        newer = list(projected_rows(rows.filter(sequence__gte=target.sequence)).order_by("sequence")[:26])
        page = list(reversed(older)) + newer
        return Response({"viewer_profile_id": str(request.user.pk), "point_id": str(point.pk),
                         "scope": projection_scope(point, request.user), "target_id": str(target.pk),
                         "results": [project_entry(request.user, row, point=point) for row in page],
                         "before_sequence": page[0].sequence,
                         "has_more": rows.filter(sequence__lt=page[0].sequence).exists()})
    def patch(self, request, entry_pk):
        entry = edit_entry(actor=request.user, entry=entry_for(request.user, entry_pk), **validate(EditSerializer, request))
        return Response({**entry_ack(entry, profile=request.user), "entry": project_entry(request.user, entry)})

    def delete(self, request, entry_pk):
        entry = delete_entry(actor=request.user, entry=entry_for(request.user, entry_pk))
        return Response({**entry_ack(entry, profile=request.user), "entry": project_entry(request.user, entry)})


class ConversationEntryReactionAPIView(EntryAPIView):
    def post(self, request, entry_pk):
        data = validate(ReactionSerializer, request)
        data.pop("client_reference", None)
        entry = react_entry(actor=request.user, entry=entry_for(request.user, entry_pk), **data)
        return Response({**entry_ack(entry, profile=request.user), "entry": project_entry(request.user, entry)})


class ConversationEntrySearchAPIView(EntryAPIView):
    def get(self, request, point_pk):
        point = point_for(request.user, point_pk)
        query = request.query_params.get("q", "").strip()
        if not 2 <= len(query) <= 200:
            raise serializers.ValidationError({"q": "Recherche de 2 à 200 caractères attendue."})
        rows = entries_for(request.user, point).filter(moderation_state="visible", body__icontains=query)
        before = integer(request, "cursor")
        if before:
            rows = rows.filter(sequence__lt=before)
        page = list(projected_rows(rows).order_by("-sequence")[:51])
        more = len(page) > 50
        page = page[:50]
        return Response({"viewer_profile_id": str(request.user.pk), "point_id": str(point.pk), "scope": projection_scope(point, request.user),
                         "results": [project_entry(request.user, row, point=point) for row in page],
                         "next_cursor": page[-1].sequence if more else None})


class ConversationEntryReceiptsAPIView(EntryAPIView):
    def get(self, request, point_pk):
        point = point_for(request.user, point_pk)
        own = point.entry_receipts.filter(profile=request.user).first()
        return Response({"delivered_sequence": own.delivered_sequence if own else 0,
                         "read_sequence": own.read_sequence if own else 0,
                         "entries": [{"id": str(row.pk), "delivery": project_entry(request.user, row, point=point)["delivery"]}
                                     for row in entries_for(request.user, point).filter(author=request.user).order_by("-sequence")[:50]]})

    def post(self, request, point_pk):
        receipt = acknowledge_entries(actor=request.user, point=point_for(request.user, point_pk), **validate(ReceiptSerializer, request))
        return Response({"delivered_sequence": receipt.delivered_sequence, "read_sequence": receipt.read_sequence})


class ConversationEntryMentionCandidatesAPIView(EntryAPIView):
    def get(self, request, point_pk):
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        from .audience_services import conversation_viewer_ids
        from .entry_services import validate_mentions
        point = point_for(request.user, point_pk)
        query = request.query_params.get("q", "").strip()[:80]
        # The global identity search is deliberately not used for private mentions.
        candidates = get_user_model().objects.filter(pk__in=conversation_viewer_ids(point.conversation), is_active=True)
        if query:
            candidates = candidates.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query))
        result = []
        for profile in candidates.order_by("pk")[:100]:
            try:
                validate_mentions(request.user, point, [profile.pk])
            except ValidationError:
                continue
            result.append({"id": str(profile.pk), "label": profile.get_full_name() or profile.username})
            if len(result) == 20:
                break
        return Response({"results": result})


class ConversationEntryReferenceAPIView(EntryAPIView):
    def get(self, request, reference_pk):
        from .entry_models import ConversationEntryReference
        from .reference_services import project_reference
        reference = get_object_or_404(ConversationEntryReference.objects.select_related("entry"), pk=reference_pk)
        entry = entry_for(request.user, reference.entry_id)
        if entry.moderation_state != "visible":
            raise NotFound("Référence inaccessible.")
        return Response(project_reference(request.user, reference))


class ConversationEntryReferenceFileAPIView(EntryAPIView):
    def get(self, request, reference_pk):
        from django.http import FileResponse, Http404
        from django.utils.text import slugify
        from .entry_models import ConversationEntryReference
        from .reference_services import authorized_target
        from sharing.document_services import export_decision_for_artifact
        from journeys.views import EXTENSION_BY_MIME
        reference = get_object_or_404(ConversationEntryReference, pk=reference_pk)
        entry = entry_for(request.user, reference.entry_id)
        if entry.moderation_state != "visible" or not reference.journey_artifact_id:
            raise NotFound("Référence inaccessible.")
        artifact = authorized_target(request.user, "journey_artifact", reference.journey_artifact_id)
        mode = request.query_params.get("mode", "view")
        if mode not in {"view", "download", "system_share"}:
            raise serializers.ValidationError("Mode inconnu.")
        if mode != "view":
            artifact, decision = export_decision_for_artifact(actor=request.user, artifact_id=artifact.pk, channel=mode)
            if decision.requires_warning and request.query_params.get("confirm") != "1":
                return Response({"confirmation_required": True}, status=409)
        try:
            handle = artifact.file.open("rb")
        except (FileNotFoundError, OSError) as exc:
            raise Http404("Document indisponible.") from exc
        filename = f"{slugify(artifact.title) or 'document'}-v{artifact.version}{EXTENSION_BY_MIME.get(artifact.mime_type, '')}"
        safe_inline = artifact.mime_type in {"application/pdf", "image/png", "image/jpeg", "text/plain"}
        response = FileResponse(handle, as_attachment=mode != "view" or not safe_inline, filename=filename, content_type=artifact.mime_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        if mode != "view":
            from sharing.analytics import emit_artifact_exported
            emit_artifact_exported(artifact=artifact, channel=mode)
        return response


class ConversationEntryReferenceOptionsAPIView(EntryAPIView):
    def get(self, request, point_pk):
        from .reference_services import authorized_target
        from journeys.collaboration_services import artifacts_for_actor
        from requirements.models import RequirementDefinition
        point = point_for(request.user, point_pk)
        context = point.conversation.context
        result = []
        journey = context.journey if context.kind == "journey" else None
        activity = journey.activity if journey else context.activity if context.kind == "activity" else None
        if journey:
            try:
                for artifact in artifacts_for_actor(actor=request.user, journey=journey).order_by("-created_at")[:20]:
                    result.append({"id": str(artifact.pk), "kind": "journey_artifact", "label": artifact.title})
                for assessment in journey.requirement_assessments.select_related("requirement")[:20]:
                    authorized_target(request.user, "journey_requirement_assessment", assessment.pk)
                    result.append({"id": str(assessment.pk), "kind": "journey_requirement_assessment", "label": assessment.requirement.title})
            except PermissionDenied:
                pass  # Other Conversation participants do not inherit case access.
        if activity:
            for definition in RequirementDefinition.objects.filter(activity=activity, status="published").order_by("position")[:20]:
                try:
                    authorized_target(request.user, "requirement_definition", definition.pk)
                except PermissionDenied:
                    continue
                result.append({"id": str(definition.pk), "kind": "requirement_definition", "label": definition.title})
        return Response({"results": result})
