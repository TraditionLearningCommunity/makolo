from django.contrib.auth import get_user_model

from accounts.models import (
    Role,
    PermissionGroup,
)

User = get_user_model()


# =========================================================
# USERS
# =========================================================

def get_users():

    return (
        User.objects
        .select_related("profile")
        .prefetch_related(
            "roles",
            "permission_groups",
        )
        .order_by("-created_at")
    )


def get_user_by_id(user_id):

    return (
        User.objects
        .select_related("profile")
        .prefetch_related(
            "roles",
            "permission_groups",
        )
        .filter(id=user_id)
        .first()
    )


# =========================================================
# ROLES
# =========================================================

def get_roles():

    return (
        Role.objects
        .filter(is_active=True)
        .order_by("priority", "name")
    )


# =========================================================
# PERMISSION GROUPS
# =========================================================

def get_permission_groups():

    return (
        PermissionGroup.objects
        .prefetch_related("roles")
        .order_by("name")
    )