from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from typing import Dict, Any
from django.conf import settings
from django.utils.text import slugify
from core.permissions import BaseAccessControl
import logging
import uuid


logger = logging.getLogger(__name__)

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Enhanced token serializer with Aparsoft specific user data.

    This serializer serves as the central point for all authentication types,
    determining user roles and permissions on the backend based on the user's
    profile and credentials. It includes organization context and role-specific
    dashboard data for the Aparsoft workflow.
    """

    username_field = User.EMAIL_FIELD

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Call parent validate method
            data = super().validate(attrs)

            # Get proper role and status from user - use actual role field for individual clients
            role = self.user.role
            status = "active" if self.user.is_active else "inactive"

            # Log the determined role for debugging
            logger.info(f"Determined role for user {self.user.email}: {role}")

            # Check if user has the expected profile based on role
            if role in ["developer", "senior_developer"] and not hasattr(
                self.user, "developer_profile"
            ):
                raise serializers.ValidationError(
                    {
                        "message": "Developer profile not found. Please contact support.",
                        "code": "profile_not_found",
                    }
                )
            elif role == "client" and not hasattr(self.user, "client_profile"):
                raise serializers.ValidationError(
                    {
                        "message": "Client profile not found. Please contact support.",
                        "code": "profile_not_found",
                    }
                )
            elif role == "project_manager" and not hasattr(
                self.user, "project_manager_profile"
            ):
                raise serializers.ValidationError(
                    {
                        "message": "Project manager profile not found. Please contact support.",
                        "code": "profile_not_found",
                    }
                )
            elif role == "account_manager" and not hasattr(
                self.user, "account_manager_profile"
            ):
                raise serializers.ValidationError(
                    {
                        "message": "Account manager profile not found. Please contact support.",
                        "code": "profile_not_found",
                    }
                )

            # Enhanced user data with organizational information
            user_data = {
                "id": self.user.id,
                "email": self.user.email,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "full_name": self.user.full_name,
                "role": role,
                "status": status,
                "subscription_tier": self.user.subscription_tier,
                "organization": None,
            }

            # Add organization data if user belongs to one
            if self.user.client_organization:
                user_data["organization"] = {
                    "id": self.user.client_organization.id,
                    "name": self.user.client_organization.name,
                    "organization_type": self.user.client_organization.organization_type,
                    "subscription_tier": self.user.client_organization.subscription_tier,
                }

            # Add role-specific summary data
            if role in ["developer", "senior_developer"] and hasattr(
                self.user, "developer_profile"
            ):
                developer = self.user.developer_profile
                user_data["developer_info"] = {
                    "experience_level": developer.experience_level,
                    "employment_type": developer.employment_type,
                    "utilization_rate": developer.utilization_rate,
                    "technical_skills_count": (
                        len(developer.technical_expertise)
                        if developer.technical_expertise
                        else 0
                    ),
                    "team": developer.team.name if developer.team else None,
                }
            elif role == "client" and hasattr(self.user, "client_profile"):
                client = self.user.client_profile
                user_data["client_info"] = {
                    "client_type": client.client_type,
                    "client_status": client.client_status,
                    "industry_sector": client.industry_sector,
                    "active_projects_count": client.active_projects_count,
                    "account_manager": (
                        client.account_manager.full_name
                        if client.account_manager
                        else None
                    ),
                }
            elif role == "project_manager" and hasattr(
                self.user, "project_manager_profile"
            ):
                pm = self.user.project_manager_profile
                user_data["project_manager_info"] = {
                    "experience_level": pm.experience_level,
                    "primary_methodology": pm.primary_methodology,
                    "active_projects_count": pm.active_projects_count,
                    "utilization_percentage": pm.utilization_percentage,
                }
            elif role == "account_manager" and hasattr(
                self.user, "account_manager_profile"
            ):
                am = self.user.account_manager_profile
                user_data["account_manager_info"] = {
                    "experience_level": am.experience_level,
                    "sales_focus": am.sales_focus,
                    "active_clients_count": am.active_clients_count,
                    "client_satisfaction_score": float(am.client_satisfaction_score),
                }
            elif role == "admin":
                user_data["admin_info"] = {"admin_level": "system"}

            data["user"] = user_data
            return data

        except AuthenticationFailed:
            raise
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                {"message": "User profile not found", "code": "profile_not_found"}
            )
        except Exception as e:
            logger.error(f"Error enriching token data: {str(e)}", exc_info=True)
            raise


class RegisterSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for user registration with Aparsoft support.
    Handles organization-specific registration with role validation.
    """

    role = serializers.CharField(
        required=True,
        help_text="User role (developer, senior_developer, project_manager, client, account_manager, admin)",
    )
    password1 = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        help_text="Password must meet system requirements",
    )
    password2 = serializers.CharField(
        write_only=True, required=True, help_text="Confirm your password"
    )
    email = serializers.EmailField(
        required=True, help_text="Primary email for account identification"
    )
    first_name = serializers.CharField(required=True, help_text="Your first name")
    last_name = serializers.CharField(required=True, help_text="Your last name")
    username = serializers.CharField(
        required=False,
        help_text="Optional username (will be generated if not provided)",
    )

    # Aparsoft specific fields
    organization_id = serializers.IntegerField(
        required=False, allow_null=True, help_text="Organization ID for client users"
    )
    subscription_tier = serializers.CharField(
        required=False, default="standard", help_text="Subscription tier for the user"
    )

    # Role-specific fields
    experience_level = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Experience level for developers, project managers, and account managers",
    )
    client_type = serializers.CharField(
        required=False, allow_null=True, help_text="Client type for client users"
    )
    industry_sector = serializers.CharField(
        required=False, allow_null=True, help_text="Industry sector for client users"
    )
    sales_focus = serializers.CharField(
        required=False, allow_null=True, help_text="Sales focus for account managers"
    )
    primary_methodology = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Primary methodology for project managers",
    )
    employment_type = serializers.CharField(
        required=False, allow_null=True, help_text="Employment type for developers"
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "username",
            "role",
            "password1",
            "password2",
            "organization_id",
            "subscription_tier",
            "experience_level",
            "client_type",
            "industry_sector",
            "sales_focus",
            "primary_methodology",
            "employment_type",
        ]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration data with Aparsoft specific checks."""
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Password fields didn't match."}
            )

        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError(
                {"email": "This email address is already registered."}
            )

        # Validate organization if provided
        organization_id = attrs.get("organization_id")
        if organization_id:
            try:
                from customers.models import Organization

                organization = Organization.objects.get(id=organization_id)
            except (ImportError, Organization.DoesNotExist):
                raise serializers.ValidationError(
                    {"organization_id": "Invalid organization ID."}
                )

        # Validate role-specific requirements
        role = attrs.get("role")
        valid_roles = [
            "developer",
            "senior_developer",
            "project_manager",
            "client",
            "account_manager",
            "admin",
        ]
        if role not in valid_roles:
            raise serializers.ValidationError(
                {"role": f"Invalid role. Must be one of: {', '.join(valid_roles)}"}
            )

        # Validate developer experience level
        if role in ["developer", "senior_developer"] and "experience_level" in attrs:
            valid_exp_levels = ["junior", "mid", "senior", "lead", "architect"]
            if attrs["experience_level"] not in valid_exp_levels:
                raise serializers.ValidationError(
                    {
                        "experience_level": f"Invalid experience level. Must be one of: {', '.join(valid_exp_levels)}"
                    }
                )

        # Validate client type
        if role == "client" and "client_type" in attrs:
            valid_client_types = [
                "individual",
                "small_business",
                "mid_market",
                "enterprise",
                "public_sector",
                "non_profit",
                "educational",
                "healthcare",
            ]
            if attrs["client_type"] not in valid_client_types:
                raise serializers.ValidationError(
                    {
                        "client_type": f"Invalid client type. Must be one of: {', '.join(valid_client_types)}"
                    }
                )

        # Validate project manager experience level
        if role == "project_manager" and "experience_level" in attrs:
            valid_pm_levels = ["entry", "intermediate", "senior", "lead", "director"]
            if attrs["experience_level"] not in valid_pm_levels:
                raise serializers.ValidationError(
                    {
                        "experience_level": f"Invalid experience level. Must be one of: {', '.join(valid_pm_levels)}"
                    }
                )

        # Validate account manager experience level
        if role == "account_manager" and "experience_level" in attrs:
            valid_am_levels = ["junior", "mid", "senior", "lead", "director"]
            if attrs["experience_level"] not in valid_am_levels:
                raise serializers.ValidationError(
                    {
                        "experience_level": f"Invalid experience level. Must be one of: {', '.join(valid_am_levels)}"
                    }
                )

        return attrs

    def generate_unique_username(self, first_name: str, last_name: str) -> str:
        """Generate a unique username with improved uniqueness guarantee."""
        try:
            # Clean and normalize the input
            first_name = "".join(e for e in first_name if e.isalnum())
            last_name = "".join(e for e in last_name if e.isalnum())
            base_username = slugify(f"{first_name} {last_name}")

            if not base_username:
                base_username = "user"

            username = base_username
            attempts = 0
            max_attempts = 10

            while User.objects.filter(username=username).exists():
                if attempts >= max_attempts:
                    username = f"user_{uuid.uuid4().hex[:10]}"
                    break

                random_string = str(uuid.uuid4())[:6]
                username = f"{base_username}{random_string}"
                attempts += 1

            return username
        except Exception as e:
            logger.error(f"Error generating username: {str(e)}", exc_info=True)
            return f"user_{uuid.uuid4().hex[:10]}"

    def create(self, validated_data: Dict[str, Any]):
        """Create new user with Aparsoft specific setup."""
        try:
            username = validated_data.get("username") or self.generate_unique_username(
                validated_data["first_name"], validated_data["last_name"]
            )

            password = validated_data.pop("password1")
            validated_data.pop("password2", None)
            validated_data.pop("username", None)

            # Extract Aparsoft specific fields
            role = validated_data.pop("role", "client")
            organization_id = validated_data.pop("organization_id", None)
            subscription_tier = validated_data.pop("subscription_tier", "standard")

            # Remove role-specific fields that will be used during profile creation
            experience_level = validated_data.pop("experience_level", None)
            client_type = validated_data.pop("client_type", None)
            industry_sector = validated_data.pop("industry_sector", None)
            sales_focus = validated_data.pop("sales_focus", None)
            primary_methodology = validated_data.pop("primary_methodology", None)
            employment_type = validated_data.pop("employment_type", None)

            # Get organization if provided
            client_organization = None
            if organization_id:
                try:
                    from customers.models import Organization

                    client_organization = Organization.objects.get(id=organization_id)
                except (ImportError, Organization.DoesNotExist):
                    pass

            user = User(
                username=username,
                email=validated_data["email"],
                first_name=validated_data["first_name"],
                last_name=validated_data["last_name"],
                role=role,
                client_organization=client_organization,
                subscription_tier=subscription_tier,
                email_verified=False,
                phone_verified=False,
                two_factor_enabled=False,
                last_active=timezone.now(),
                login_count=0,
                social_auth_providers={
                    "connections": {},
                    "active_providers": [],
                    "default_login": None,
                },
            )

            user.set_password(password)
            user.save()

            # Store role-specific data in the context for profile creation later
            self.context["role_data"] = {
                "experience_level": experience_level,
                "client_type": client_type,
                "industry_sector": industry_sector,
                "sales_focus": sales_focus,
                "primary_methodology": primary_methodology,
                "employment_type": employment_type,
            }

            logger.info(
                f"Created new {role} user: {user.email} for organization: {client_organization.name if client_organization else 'None'}"
            )
            return user

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}", exc_info=True)
            raise


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Custom token refresh serializer that accepts the refresh token from cookie
    """

    refresh = serializers.CharField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            attrs["refresh"] = refresh_token

        if not attrs.get("refresh"):
            raise InvalidToken("No valid refresh token found")

        return super().validate(attrs)


class SocialAuthSerializer(serializers.Serializer):
    """
    Serializer for handling OAuth authentication
    """

    provider = serializers.CharField(required=True)
    code = serializers.CharField(required=True)
    redirect_uri = serializers.CharField(required=True)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change
    """

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password": "Password fields didn't match."}
            )

        try:
            validate_password(attrs["new_password"])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        return attrs
