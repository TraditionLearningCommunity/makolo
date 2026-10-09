"""Reusable technical Admin boundaries; not domain authorization.

These ModelAdmin gates prevent raw ORM form changes in the technical surface.
Legitimate mutations remain in their owner services and product/Platform views.
"""
from django.contrib import admin


class TechnicalReadOnlyAdmin(admin.ModelAdmin):
    """Inspect existing rows; no create, edit, delete or bulk delete."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
