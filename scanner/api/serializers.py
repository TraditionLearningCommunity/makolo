from django.contrib.auth import get_user_model

from rest_framework import serializers

from accounts.api.permissions import user_has_role
from activities.models import Activity, Occurrence
from events.models import Event
from scanner.models import EventAccessGate, ScanLog, ScannerAssignment
from scanner.permissions import (
    user_can_manage_activity_scanner_assignments,
    user_can_manage_scanner_assignments,
)


User = get_user_model()


class ScannerEventSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)

    class Meta:
        model = Event
        fields = ["id", "title", "slug", "status", "start_at", "end_at", "venue_name"]
        read_only_fields = fields


class ScannerUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name"]
        read_only_fields = fields


class EventAccessGateSerializer(serializers.ModelSerializer):
    event = ScannerEventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all(), write_only=True)
    created_by = ScannerUserSerializer(read_only=True)

    class Meta:
        model = EventAccessGate
        fields = [
            "id", "event", "event_id", "name", "slug", "description", "is_active",
            "throughput_target_per_minute", "warning_rejection_rate", "priority", "notes",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        if request and event and not user_can_manage_scanner_assignments(request.user, event):
            raise serializers.ValidationError({"event_id": "Vous ne pouvez gérer les portes que pour vos événements autorisés."})
        return attrs


class ScannerAssignmentSerializer(serializers.ModelSerializer):
    event = ScannerEventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(
        source="event", queryset=Event.objects.select_related("activity"), write_only=True,
        required=False, allow_null=True,
    )
    activity_id = serializers.PrimaryKeyRelatedField(
        source="activity", queryset=Activity.objects.all(), write_only=True,
        required=False, allow_null=True,
    )
    occurrence_id = serializers.PrimaryKeyRelatedField(
        source="occurrence", queryset=Occurrence.objects.select_related("activity"), write_only=True,
        required=False, allow_null=True,
    )
    agent = ScannerUserSerializer(read_only=True)
    agent_id = serializers.PrimaryKeyRelatedField(source="agent", queryset=User.objects.filter(is_active=True), write_only=True)
    access_gate = EventAccessGateSerializer(read_only=True)
    access_gate_id = serializers.PrimaryKeyRelatedField(
        source="access_gate", queryset=EventAccessGate.objects.all(), write_only=True,
        required=False, allow_null=True,
    )
    assigned_by = ScannerUserSerializer(read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScannerAssignment
        fields = [
            "id", "event", "event_id", "activity_id", "occurrence_id", "agent", "agent_id",
            "access_gate", "access_gate_id", "assigned_by", "label", "is_active", "is_current",
            "valid_from", "valid_until", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "assigned_by", "is_current", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        activity = attrs.get("activity", getattr(instance, "activity", None))
        occurrence = attrs.get("occurrence", getattr(instance, "occurrence", None))
        agent = attrs.get("agent", getattr(instance, "agent", None))
        access_gate = attrs.get("access_gate", getattr(instance, "access_gate", None))
        valid_from = attrs.get("valid_from", getattr(instance, "valid_from", None))
        valid_until = attrs.get("valid_until", getattr(instance, "valid_until", None))

        if event is not None:
            if agent is not None and not (
                agent.is_staff
                or user_has_role(agent, "scanner-agent", legacy_flag="is_scanner_agent")
            ):
                raise serializers.ValidationError(
                    {"agent_id": "Cet utilisateur doit avoir le rôle scanner-agent."}
                )
            if not event.activity_id:
                raise serializers.ValidationError({"event_id": "Cet Event n’a pas de projection Activity canonique."})
            if activity is not None and activity.pk != event.activity_id:
                raise serializers.ValidationError({"activity_id": "Cette Activity ne correspond pas à l’Event."})
            activity = event.activity
            attrs["activity"] = activity
            if occurrence is None:
                occurrence = (
                    activity.occurrences.filter(start_at=event.start_at, end_at=event.end_at)
                    .order_by("id").first()
                )
                if occurrence is None:
                    raise serializers.ValidationError({"event_id": "L’Occurrence canonique de cet Event est introuvable."})
                attrs["occurrence"] = occurrence
        if activity is None:
            raise serializers.ValidationError({"activity_id": "Une Activity est obligatoire."})
        if occurrence is not None and occurrence.activity_id != activity.pk:
            raise serializers.ValidationError({"occurrence_id": "Cette Occurrence appartient à une autre Activity."})
        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError({"valid_until": "La fin doit être postérieure au début."})
        if access_gate:
            if event is None or access_gate.event_id != event.pk:
                raise serializers.ValidationError({"access_gate_id": "Cette porte appartient à un autre événement."})
        if request:
            if event is not None and user_can_manage_scanner_assignments(request.user, event):
                return attrs
            if not user_can_manage_activity_scanner_assignments(request.user, activity):
                raise serializers.ValidationError({"activity_id": "Vous ne pouvez gérer les affectations que dans cette Activity."})
        return attrs


class ScanLogSerializer(serializers.ModelSerializer):
    event = ScannerEventSerializer(read_only=True)
    scanner = ScannerUserSerializer(read_only=True)
    access_gate = EventAccessGateSerializer(read_only=True)
    ticket_id = serializers.UUIDField(source="ticket.id", read_only=True, allow_null=True)
    ticket_code = serializers.UUIDField(source="ticket.code", read_only=True, allow_null=True)
    holder_name = serializers.CharField(source="ticket.holder_name", read_only=True, allow_null=True)
    ticket_type = serializers.CharField(source="ticket.ticket_type.name", read_only=True, allow_null=True)
    result_label = serializers.CharField(source="get_result_display", read_only=True)
    accepted = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScanLog
        fields = [
            "id", "event", "scanner", "access_gate", "ticket_id", "ticket_code", "holder_name",
            "ticket_type", "result", "result_label", "accepted", "message", "gate",
            "client_reference", "scanned_at",
        ]
        read_only_fields = fields


class ScanRequestSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all())
    access_gate_id = serializers.PrimaryKeyRelatedField(
        source="access_gate", queryset=EventAccessGate.objects.all(), required=False, allow_null=True,
    )
    token = serializers.CharField(max_length=1024, trim_whitespace=True)
    client_reference = serializers.CharField(max_length=64, required=False, allow_blank=True)
    gate = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs):
        event = attrs.get("event")
        access_gate = attrs.get("access_gate")
        if event and access_gate and access_gate.event_id != event.pk:
            raise serializers.ValidationError({"access_gate_id": "Cette porte appartient à un autre événement."})
        return attrs
