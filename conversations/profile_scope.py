from django.core.exceptions import PermissionDenied


class ConversationProfileScopeMixin:
    """An old tab/repository must never act as a newly selected account."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        expected = request.headers.get("X-Makolo-Profile")
        if expected and expected != str(request.user.pk):
            raise PermissionDenied("Le Profile actif a changé. Rechargez cette vue.")
