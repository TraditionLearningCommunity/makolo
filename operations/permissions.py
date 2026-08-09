def user_can_access_operations(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)
