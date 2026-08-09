from rest_framework import serializers

from automation.models import CRMWorkflow, CRMWorkflowAction, CRMWorkflowRun


class CRMWorkflowActionSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = CRMWorkflowAction
        fields = [
            "id",
            "position",
            "kind",
            "kind_label",
            "delay_minutes",
            "template_id",
            "tag_id",
            "title",
            "message",
            "marketing_action",
            "is_active",
        ]
        read_only_fields = ["id", "kind_label"]


class CRMWorkflowSerializer(serializers.ModelSerializer):
    trigger_label = serializers.CharField(source="get_trigger_display", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    segment_name = serializers.CharField(source="segment.name", read_only=True)
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    actions = CRMWorkflowActionSerializer(many=True, read_only=True)
    run_count = serializers.IntegerField(source="runs.count", read_only=True)

    class Meta:
        model = CRMWorkflow
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "name",
            "description",
            "trigger",
            "trigger_label",
            "event_id",
            "event_title",
            "segment_id",
            "segment_name",
            "ticket_type_id",
            "ticket_type_name",
            "min_order_amount",
            "currency",
            "event_offset_minutes",
            "trigger_grace_minutes",
            "is_active",
            "created_at",
            "updated_at",
            "run_count",
            "actions",
        ]
        read_only_fields = [
            "id",
            "organization_name",
            "trigger_label",
            "event_title",
            "segment_name",
            "ticket_type_name",
            "created_at",
            "updated_at",
            "run_count",
            "actions",
        ]


class CRMWorkflowCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True)
    trigger = serializers.CharField(max_length=32)
    event_id = serializers.UUIDField(required=False, allow_null=True)
    segment_id = serializers.UUIDField(required=False, allow_null=True)
    ticket_type_id = serializers.UUIDField(required=False, allow_null=True)
    min_order_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    event_offset_minutes = serializers.IntegerField(required=False, min_value=0, max_value=525600)
    trigger_grace_minutes = serializers.IntegerField(required=False, min_value=1, max_value=10080)
    is_active = serializers.BooleanField(required=False)


class CRMWorkflowActionCreateSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=1)
    kind = serializers.CharField(max_length=32)
    delay_minutes = serializers.IntegerField(required=False, min_value=0, max_value=525600)
    template_id = serializers.UUIDField(required=False, allow_null=True)
    tag_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True, max_length=180)
    message = serializers.CharField(required=False, allow_blank=True)
    marketing_action = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class CRMWorkflowRunSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    contact_email = serializers.CharField(source="contact.email", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CRMWorkflowRun
        fields = [
            "id",
            "workflow_id",
            "workflow_name",
            "contact_id",
            "contact_email",
            "event_id",
            "event_title",
            "order_id",
            "order_reference",
            "source_type",
            "source_id",
            "status",
            "status_label",
            "context",
            "skip_reason",
            "error",
            "started_at",
            "completed_at",
            "created_at",
        ]
