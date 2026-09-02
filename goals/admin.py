from django.contrib import admin

from .models import PersonalGoal


@admin.register(PersonalGoal)
class PersonalGoalAdmin(admin.ModelAdmin):
    list_display = ("profile", "goal_type", "target_value", "status", "period_start", "period_end")
    list_filter = ("goal_type", "status")
    search_fields = ("profile__email", "profile__username")
    readonly_fields = ("completed_at", "created_at", "updated_at")
