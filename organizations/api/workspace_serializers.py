from rest_framework import serializers

from organizations.models import SpaceArchetype


class SpaceWorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    archetype = serializers.ChoiceField(
        choices=SpaceArchetype.choices,
        default=SpaceArchetype.GENERIC,
    )
    description = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=50)
    public_profile = serializers.BooleanField(required=False, default=True)


class SpaceWorkspaceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180, required=False)
    archetype = serializers.ChoiceField(choices=SpaceArchetype.choices, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=50)
    public_profile = serializers.BooleanField(required=False)


class SpaceOwnershipTransferSerializer(serializers.Serializer):
    target_membership_id = serializers.UUIDField()
    relinquish_current_owner = serializers.BooleanField(default=True)
