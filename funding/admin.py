from django.contrib import admin

from .models import FundingContribution, FundingDetails


@admin.register(FundingDetails)
class FundingDetailsAdmin(admin.ModelAdmin):
    list_display = ("activity", "currency", "target_amount", "opens_at", "closes_at")
    search_fields = ("activity__title", "activity__space__name", "activity__owner_profile__email")
    list_select_related = ("activity",)


@admin.register(FundingContribution)
class FundingContributionAdmin(admin.ModelAdmin):
    list_display = ("funding", "contributor_profile", "amount", "currency", "payment_obligation", "created_at")
    search_fields = ("funding__activity__title", "contributor_profile__email", "client_reference")
    readonly_fields = ("funding", "contributor_profile", "amount", "currency", "client_reference", "payment_obligation", "created_at")
    list_select_related = ("funding", "funding__activity", "contributor_profile", "payment_obligation")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
