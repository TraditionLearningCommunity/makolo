from django.contrib.auth import get_user_model

from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import NotificationPreference, PermissionGroup, Role
from accounts.services import (
    change_password,
    delete_account,
    request_password_reset,
    reset_password,
)

from .permissions import IsAdmin, IsSelfOrAdmin
from .selectors import get_permission_groups, get_roles, get_users
from .serializers import (
    AccountDeleteSerializer,
    NotificationPreferenceSerializer,
    PasswordChangeSerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    PermissionGroupSerializer,
    RegisterSerializer,
    RoleSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from .throttles import LoginThrottle, PasswordResetThrottle, RegistrationThrottle

User = get_user_model()


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Compte créé. Connectez-vous pour obtenir vos jetons d’authentification.",
                "user": UserDetailSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]


class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"refresh": "Le refresh token est obligatoire."})

        try:
            token = RefreshToken(refresh_token)
            if str(token.get("user_id")) != str(request.user.pk):
                raise TokenError("Token does not belong to the current user.")
            token.blacklist()
        except (TokenError, TypeError, ValueError) as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"refresh": "Refresh token invalide."}) from exc

        return Response({"message": "Déconnexion effectuée."})


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            UserDetailSerializer(request.user, context={"request": request}).data
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_users()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
                "message": "Profil mis à jour.",
                "user": UserDetailSerializer(
                    request.user,
                    context={"request": request},
                ).data,
            }
        )


class PasswordForgotAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(email=serializer.validated_data["email"])
        return Response(
            {
                "message": (
                    "Si un compte actif correspond à cette adresse, un e-mail de réinitialisation a été envoyé."
                )
            }
        )


class PasswordResetAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_password(
            uid=serializer.validated_data["uid"],
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"message": "Mot de passe réinitialisé. Connectez-vous à nouveau."})


class PasswordChangeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"message": "Mot de passe modifié. Reconnectez-vous sur vos appareils."})


class NotificationPreferencesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _preference(self, request):
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return preference

    def get(self, request):
        return Response(NotificationPreferenceSerializer(self._preference(request)).data)

    def patch(self, request):
        preference = self._preference(request)
        serializer = NotificationPreferenceSerializer(
            preference,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AccountDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AccountDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = delete_account(
            user=request.user,
            current_password=serializer.validated_data["password"],
        )
        return Response(result, status=status.HTTP_200_OK)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_roles()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class PermissionGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_permission_groups()
    serializer_class = PermissionGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
