from django.contrib.auth import get_user_model

from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PermissionGroup, Role

from .permissions import IsAdmin, IsSelfOrAdmin
from .selectors import get_permission_groups, get_roles, get_users
from .serializers import (
    PermissionGroupSerializer,
    RegisterSerializer,
    RoleSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": (
                    "Account created successfully. "
                    "Use the login endpoint to obtain authentication tokens."
                ),
                "user": UserDetailSerializer(
                    user,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            if str(token.get("user_id")) != str(request.user.pk):
                raise TokenError(
                    "Token does not belong to the current user."
                )

            token.blacklist()
        except (TokenError, TypeError, ValueError):
            return Response(
                {"error": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message": "Logged out successfully."})


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserDetailSerializer(
            request.user,
            context={"request": request},
        )
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_users()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = [
        "get",
        "patch",
        "delete",
        "head",
        "options",
    ]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == "list":
            return UserListSerializer
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserDetailSerializer

    def get_permissions(self):
        if self.action in ["list", "destroy"]:
            permission_classes = [IsAdmin]
        elif self.action in ["retrieve", "update", "partial_update"]:
            permission_classes = [IsSelfOrAdmin]
        else:
            permission_classes = [IsAdmin]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()

        if not self.request.user.is_staff:
            return queryset.filter(pk=self.request.user.pk)

        search = self.request.query_params.get("search")
        verified = self.request.query_params.get("verified")
        role = self.request.query_params.get("role")

        if search:
            queryset = queryset.filter(email__icontains=search)

        if verified == "true":
            queryset = queryset.filter(is_verified=True)
        elif verified == "false":
            queryset = queryset.filter(is_verified=False)

        if role:
            queryset = queryset.filter(roles__code=role)

        return queryset.distinct()


class UpdateProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Profile updated successfully.",
                "user": UserDetailSerializer(
                    request.user,
                    context={"request": request},
                ).data,
            }
        )


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_roles()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class PermissionGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_permission_groups()
    serializer_class = PermissionGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
