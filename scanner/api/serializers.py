from django.contrib.auth import get_user_model

from rest_framework import serializers

from accounts.api.permissions import user_has_role
from events.models import Event
from scanner.models import ScanLog, ScannerAssignment
from scanner.permissions import user_can_manage_scanner_assignments


User = get_user_model()


class ScannerEventSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "status",
            "start_at",
            "end_at",
            "venue_name",
        ]
        read_only_fields = fields


class ScannerUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name"]
        read_only_fields = fields


class ScannerAssignmentSerializer(serializers.ModelSerializer):
    event = ScannerEventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(
        source="event",
        queryset=Event.objects.all(),
        write_only=True,
    )
    agent = ScannerUserSerializer(read_only=True)
    agent_id = serializers.PrimaryKeyRelatedField(
        source="agent",
        queryset=User.objects.filter(is_active=True),
        write_only=True,
    )
    assigned_by = ScannerUserSerializer(read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScannerAssignment
        fields = [
            "id",
            "event",
            "event_id",
            "agent",
            "agent_id",
            "assigned_by",
            "label",
            "is_active",
            "is_current",
            "valid_from",
            "valid_until",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assigned_by",
            "is_current",
            "created_at",
            "updated_at",
        ]

    def validate_agent_id(self, agent):
        if not (
            agent.is_staff
            or user_has_role(
                agent,
                "scanner-agent",
                legacy_flag="is_scanner_agent",
            )
        ):
            raise serializers.ValidationError(
                "Cet utilisateur doit avoir le rôle scanner-agent."
            )
        return agent

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        valid_from = attrs.get("valid_from", getattr(instance, "valid_from", None))
        valid_until = attrs.get("valid_until", getattr(instance, "valid_until", None))

        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError(
                {"valid_until": "La fin doit être postérieure au début."}
            )

        if request and event and not user_can_manage_scanner_assignments(
            request.user,
            event,
        ):
            raise serializers.ValidationError(
                {"event_id": "Vous ne pouvez gérer que vos propres événements."}
            )
        return attrs


class ScanLogSerializer(serializers.ModelSerializer):
    event = ScannerEventSerializer(read_only=True)
    scanner = ScannerUserSerializer(read_only=True)
    ticket_id = serializers.UUIDField(source="ticket.id", read_only=True, allow_null=True)
    ticket_code = serializers.UUIDField(
        source="ticket.code",
        read_only=True,
        allow_null=True,
    )
    holder_name = serializers.CharField(
        source="ticket.holder_name",
        read_only=True,
        allow_null=True,
    )
    ticket_type = serializers.CharField(
        source="ticket.ticket_type.name",
        read_only=True,
        allow_null=True,
    )
    result_label = serializers.CharField(source="get_result_display", read_only=True)
    accepted = serializers.BooleanField(read_only=True)

    class Meta:
        model = ScanLog
        fields = [
            "id",
            "event",
            "scanner",
            "ticket_id",
            "ticket_code",
            "holder_name",
            "ticket_type",
            "result",
            "result_label",
            "accepted",
            "message",
            "gate",
            "client_reference",
            "scanned_at",
        ]
        read_only_fields = fields


class ScanRequestSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(
        source="event",
        queryset=Event.objects.all(),
    )
    token = serializers.CharField(max_length=1024, trim_whitespace=True)
    client_reference = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
    )
    gate = serializers.CharField(max_length=120, required=False, allow_blank=True)
