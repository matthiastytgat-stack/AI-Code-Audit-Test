# /home/ram/aparsoft/backend/apps/accounts/api/urls.py

"""
URL configuration for accounts API.
Provides router-based URL patterns for all viewsets in the accounts app.
"""
from django.urls import path, include
from rest_framework_simplejwt.views import TokenVerifyView
from rest_framework.routers import DefaultRouter

from .views import (
    # Auth viewsets
    CustomTokenObtainPairView,
    LogoutView,
    RegisterView,
    # SocialAuthView, UserInfoView, PasswordChangeView,
    CSRFTokenView,
    EmailVerificationView,
    PasswordResetView,
    OrganizationRegisterView,
    # CustomUser viewsets
    CustomUserViewSet,
    UserContactViewSet,
    # Developer viewsets
    DeveloperProfileViewSet,
    # Client viewsets
    ClientProfileViewSet,
    # ProjectManager viewsets
    ProjectManagerProfileViewSet,
    # AccountManager viewsets
    AccountManagerProfileViewSet,
    # Team viewsets
    TeamViewSet,
    # Profile avatar views
    ProfileAvatarView,
)

app_name = "accounts"

# Initialize the default router
router = DefaultRouter()

# Register CustomUser viewsets
router.register(r"users", CustomUserViewSet, basename="user")
router.register(r"user-contacts", UserContactViewSet, basename="user-contact")

# Register Developer viewsets
router.register(r"developers", DeveloperProfileViewSet, basename="developer")

# Register Client viewsets
router.register(r"clients", ClientProfileViewSet, basename="client")

# Register ProjectManager viewsets
router.register(
    r"project-managers", ProjectManagerProfileViewSet, basename="project-manager"
)

# Register AccountManager viewsets
router.register(
    r"account-managers", AccountManagerProfileViewSet, basename="account-manager"
)

# Register Team viewsets
router.register(r"teams", TeamViewSet, basename="team")

# URL patterns
urlpatterns = [
    # Router generated URLs
    path("", include(router.urls)),
    # Authentication endpoints
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path(
        "auth/organization-register/",
        OrganizationRegisterView.as_view(),
        name="auth_organization_register",
    ),
    # path('auth/social/', SocialAuthView.as_view(), name='auth_social'),
    # path('auth/me/', UserInfoView.as_view(), name='auth_user_info'),
    # path('auth/password/change/', PasswordChangeView.as_view(),
    #      name='auth_password_change'),
    path(
        "auth/password/reset/", PasswordResetView.as_view(), name="auth_password_reset"
    ),
    path(
        "auth/email/verify/", EmailVerificationView.as_view(), name="auth_email_verify"
    ),
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf_token"),
    # Profile management endpoints
    path("users/profile_image/", ProfileAvatarView.as_view(), name="profile_image"),
]
