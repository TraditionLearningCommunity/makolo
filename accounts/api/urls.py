from django.urls import path, include

from rest_framework.routers import DefaultRouter

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    RegisterAPIView,
    LogoutAPIView,
    MeAPIView,
    UpdateProfileAPIView,
    UserViewSet,
    RoleViewSet,
    PermissionGroupViewSet,
)


router = DefaultRouter()

router.register(
    r'users',
    UserViewSet,
    basename='users'
)

router.register(
    r'roles',
    RoleViewSet,
    basename='roles'
)

router.register(
    r'permission-groups',
    PermissionGroupViewSet,
    basename='permission-groups'
)


urlpatterns = [

    # =====================================================
    # AUTH
    # =====================================================

    path(
        "auth/register/",
        RegisterAPIView.as_view(),
        name="register",
    ),

    path(
        "auth/login/",
        TokenObtainPairView.as_view(),
        name="login",
    ),

    path(
        "auth/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path(
        "auth/logout/",
        LogoutAPIView.as_view(),
        name="logout",
    ),

    path(
        "auth/me/",
        MeAPIView.as_view(),
        name="me",
    ),

    path(
        "auth/profile/update/",
        UpdateProfileAPIView.as_view(),
        name="profile-update",
    ),

    # =====================================================
    # ROUTER
    # =====================================================

    path(
        "",
        include(router.urls)
    ),
]