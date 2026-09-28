from django.contrib.auth.backends import ModelBackend

from .models import User
from .validators import normalize_makolo_username


class MakoloAccountBackend(ModelBackend):
    """Authenticate local Makolo accounts with identifier or e-mail.

    The public login field remains a single value. E-mail is optional and is
    never the canonical Profile identity.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get(User.USERNAME_FIELD)
        if not login or not password:
            return None

        raw_login = str(login).strip()
        try:
            if "@" in raw_login:
                user = User.objects.get(email__iexact=raw_login.lower())
            else:
                user = User.objects.get(
                    username__iexact=normalize_makolo_username(raw_login)
                )
        except User.DoesNotExist:
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
