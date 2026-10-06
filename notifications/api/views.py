from django.utils import timezone
from rest_framework import generics, permissions, response, views
from rest_framework.exceptions import NotFound

from core.api.privacy import PrivateNoStoreMixin

from notifications.models import Notification
from notifications.push import register_push_endpoint, revoke_push_endpoint
from notifications.selectors import get_notifications_for_user

from .serializers import (
    NotificationSerializer,
    PushEndpointRegistrationSerializer,
    PushEndpointRevokeSerializer,
    PushEndpointSerializer,
)



class NotificationListAPIView(PrivateNoStoreMixin, generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_notifications_for_user(self.request.user)
        if self.request.query_params.get("filter") == "unread":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


class NotificationDetailAPIView(PrivateNoStoreMixin, generics.RetrieveAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return get_notifications_for_user(self.request.user)


class NotificationUnreadCountAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = get_notifications_for_user(request.user).filter(read_at__isnull=True).count()
        return response.Response({"unread_count": count})


class NotificationMarkReadAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_notifications_for_user(request.user).filter(pk=pk).first()
        if not notification:
            raise NotFound("Notification introuvable.")
        notification.mark_read()
        return response.Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        updated = get_notifications_for_user(request.user).filter(read_at__isnull=True).update(
            read_at=now,
            updated_at=now,
        )
        return response.Response({"updated": updated})


class PushEndpointAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushEndpointRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            endpoint = register_push_endpoint(
                user=request.user,
                **serializer.validated_data,
            )
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": str(exc)}) from exc
        return response.Response(PushEndpointSerializer(endpoint).data)

    def delete(self, request):
        serializer = PushEndpointRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoked = revoke_push_endpoint(
            user=request.user,
            **serializer.validated_data,
        )
        return response.Response({"revoked": bool(revoked)})
