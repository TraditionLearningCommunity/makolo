from django.contrib import admin

from .models import ActionNeed, ActionNetworkBlock, ActionProposal, Contribution


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("kind", "author_profile", "group", "activity", "visibility", "status", "created_at")
    list_filter = ("kind", "visibility", "status")
    search_fields = ("author_profile__email", "author_profile__username", "body")
    readonly_fields = ("created_at", "updated_at", "edited_at", "moderated_at")


@admin.register(ActionNeed)
class ActionNeedAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_profile", "space", "match_kind", "candidate_kind", "status", "created_by", "created_at")
    list_filter = ("status", "match_kind", "candidate_kind", "visibility", "intake_policy")
    search_fields = ("title", "description", "owner_profile__username", "space__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ActionProposal)
class ActionProposalAdmin(admin.ModelAdmin):
    list_display = ("need", "candidate_profile", "candidate_space", "direction", "initiated_by", "status", "created_at")
    list_filter = ("status", "direction")
    search_fields = ("need__title", "candidate_profile__username", "candidate_space__name", "initiated_by__username")
    readonly_fields = ("created_at", "updated_at", "responded_at", "cancelled_at")


@admin.register(ActionNetworkBlock)
class ActionNetworkBlockAdmin(admin.ModelAdmin):
    list_display = ("blocker_profile", "blocker_space", "blocked_profile", "blocked_space", "created_by", "created_at")
    readonly_fields = ("created_at",)
