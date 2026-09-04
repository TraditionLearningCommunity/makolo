from django.contrib import admin

from .models import ActivityTopic, ProfileInterest, ProfileOpenTo, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("label", "code")
    ordering = ("label", "code")


@admin.register(ProfileInterest)
class ProfileInterestAdmin(admin.ModelAdmin):
    list_display = ("profile", "topic", "is_public", "created_at")
    list_filter = ("is_public", "topic")
    search_fields = ("profile__email", "profile__username", "topic__label", "topic__code")


@admin.register(ProfileOpenTo)
class ProfileOpenToAdmin(admin.ModelAdmin):
    list_display = ("profile", "kind", "topic", "is_active", "is_public", "is_searchable")
    list_filter = ("kind", "is_active", "is_public", "is_searchable")
    search_fields = ("profile__email", "profile__username", "topic__label")


@admin.register(ActivityTopic)
class ActivityTopicAdmin(admin.ModelAdmin):
    list_display = ("activity", "topic", "created_at")
    list_filter = ("topic",)
    search_fields = ("activity__title", "topic__label", "topic__code")
