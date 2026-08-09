from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import OrganizationVerificationStatus
from operations.models import ModerationCase, OperationsIncident, WorkerHeartbeat
from operations.services import create_incident, update_incident


User = get_user_model()


class OperationsIncidentSerializer(serializers.ModelSerializer):
    opened_by_email = serializers.EmailField(source="opened_by.email", read_only=True)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = OperationsIncident
        fields = [
            "id",
            "title",
            "category",
            "severity",
            "status",
            "organization",
            "organization_name",
            "event",
            "event_title",
            "payment",
            "scan_log",
            "description",
            "resolution",
            "assigned_to",
            "assigned_to_email",
            "opened_by_email",
            "detected_at",
            "acknowledged_at",
            "resolved_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "opened_by_email",
            "assigned_to_email",
            "organization_name",
            "event_title",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]

    def validate_assigned_to(self, value):
        if value is not None and not value.is_staff:
            raise serializers.ValidationError("L'assignation est réservée au staff Makolo.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        return create_incident(actor=request.user, **validated_data)

    def update(self, instance, validated_data):
        request = self.context["request"]
        immutable = {"title", "category", "organization", "event", "payment", "scan_log", "description", "metadata", "detected_at"}
        attempted = immutable.intersection(validated_data)
        if attempted:
            raise serializers.ValidationError(
                {field: "Ce champ est immuable via cette route après création." for field in attempted}
            )
        return update_incident(
            incident=instance,
            actor=request.user,
            status=validated_data.get("status", instance.status),
            severity=validated_data.get("severity", instance.severity),
            assigned_to=validated_data.get("assigned_to", instance.assigned_to),
            resolution=validated_data.get("resolution", instance.resolution),
        )


class OrganizationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrganizationVerificationStatus.choices)
    reason = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class EventModerationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            ("unlist", "Retirer de la découverte publique"),
            ("private", "Rendre privé"),
            ("cancel", "Annuler"),
            ("restore_public", "Restaurer la visibilité publique"),
        ]
    )
    reason = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class ModerationCaseSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    opened_by_email = serializers.EmailField(source="opened_by.email", read_only=True)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)

    class Meta:
        model = ModerationCase
        fields = [
            "id",
            "target_type",
            "organization",
            "organization_name",
            "event",
            "event_title",
            "severity",
            "status",
            "reason",
            "outcome",
            "opened_by_email",
            "assigned_to_email",
            "closed_at",
            "created_at",
            "updated_at",
        ]


class WorkerHeartbeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerHeartbeat
        fields = [
            "id",
            "worker_name",
            "instance_id",
            "state",
            "last_seen_at",
            "last_cycle_started_at",
            "last_cycle_finished_at",
            "last_error",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
