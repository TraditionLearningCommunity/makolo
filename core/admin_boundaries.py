"""Reusable technical Admin boundaries; not domain authorization.

These ModelAdmin gates prevent raw ORM form changes in the technical surface.
Legitimate mutations remain in their owner services and product/Platform views.
"""
from django.contrib import admin


class TechnicalReadOnlyAdmin(admin.ModelAdmin):
    """Inspect existing rows; no create, edit, delete or bulk delete."""

    def get_readonly_fields(self, request, obj=None):
        declared = super().get_readonly_fields(request, obj)
        return tuple(dict.fromkeys((*declared, *(field.name for field in self.model._meta.fields))))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TechnicalSuperuserReadOnlyAdmin(TechnicalReadOnlyAdmin):
    """Exceptional forensic access to private data, never generic staff access."""

    def has_module_permission(self, request):
        user = request.user
        return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)
