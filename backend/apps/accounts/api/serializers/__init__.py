"""
Serializers package for accounts API.
"""

from .auth_serializers import (
    CustomTokenObtainPairSerializer,
    CustomTokenRefreshSerializer,
    RegisterSerializer,
    SocialAuthSerializer,
    PasswordChangeSerializer,
)

# CustomUser serializers
from .custom_user_serializers import (
    CustomUserSerializer,
    CustomUserMinimalSerializer,
    UserContactSerializer,
    UserContactMinimalSerializer,
)

__all__ = [
    # Auth serializers
    "CustomTokenObtainPairSerializer",
    "CustomTokenRefreshSerializer",
    "RegisterSerializer",
    "SocialAuthSerializer",
    "PasswordChangeSerializer",
    # CustomUser serializers
    "CustomUserSerializer",
    "CustomUserMinimalSerializer",
    "UserContactSerializer",
    "UserContactMinimalSerializer",
]
