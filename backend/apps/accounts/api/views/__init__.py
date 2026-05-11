# /home/ram/aparsoft/backend/apps/accounts/api/views/__init__.py

"""
ViewSets package for accounts API.
"""
# Auth view
from .auth_views import (
    CustomTokenObtainPairView,
    LogoutView,
)

# Auth register view
from .auth_register_views import (
    RegisterView,
    OrganizationRegisterView,
    CSRFTokenView,
)

# Auth password reset view
from .auth_password_reset_views import (
    PasswordResetView,
    PasswordResetConfirmView,
    EmailVerificationView,
    PasswordChangeView,
)

# CustomUser viewsets
from .custom_user_views import (
    CustomUserViewSet,
    UserContactViewSet,
)

# Developer viewsets
from .developer_views import (
    DeveloperProfileViewSet,
)

# Client viewsets
from .client_views import (
    ClientProfileViewSet,
)

# ProjectManager viewsets
from .project_manager_views import (
    ProjectManagerProfileViewSet,
)

# AccountManager viewsets
from .account_manager_views import (
    AccountManagerProfileViewSet,
)

# Team viewsets
from .team_views import (
    TeamViewSet,
)

# Profile avatar views
from .profile_avatar_views import (
    ProfileAvatarView,
)

__all__ = [
    # Auth viewsets
    "CustomTokenObtainPairView",
    "LogoutView",
    "RegisterView",
    "PasswordChangeView",
    "CSRFTokenView",
    "EmailVerificationView",
    "PasswordResetView",
    "OrganizationRegisterView",
    "PasswordResetConfirmView",
    # CustomUser viewsets
    "CustomUserViewSet",
    "UserContactViewSet",
    # Developer viewsets
    "DeveloperProfileViewSet",
    # Client viewsets
    "ClientProfileViewSet",
    # ProjectManager viewsets
    "ProjectManagerProfileViewSet",
    # AccountManager viewsets
    "AccountManagerProfileViewSet",
    # Team viewsets
    "TeamViewSet",
    # Profile avatar views
    "ProfileAvatarView",
]
