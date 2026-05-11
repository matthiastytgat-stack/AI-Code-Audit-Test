# /home/ram/aparsoft/backend/apps/accounts/api/views/auth_views.py

"""
Enhanced Authentication Views for Aparsoft

This module provides comprehensive authentication functionality including:
- Role-based login with appropriate user context
- Enhanced registration with automatic profile creation
- User validation
- Secure cookie-based session management
- Profile completion workflows
- Administrative user creation

Key Features:
1. Automatic profile creation after registration based on user role
2. Enhanced security with proper error handling
3. Role-specific dashboard redirection after login
4. Integration with Aparsoft workflow
"""

from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
import logging
from rest_framework.throttling import AnonRateThrottle
from typing import Dict, Any
from decouple import config

# Import enhanced serializers
from ..serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
)

# Import models from Aparsoft accounts
from ...models import (
    CustomUser,
    UserContact,
    DeveloperProfile,
    ClientProfile,
    ProjectManagerProfile,
    AccountManagerProfile,
    Team,
)

# Import permissions
from core.permissions import BaseAccessControl

logger = logging.getLogger(__name__)
User = get_user_model()


@method_decorator([ensure_csrf_cookie], name="dispatch")
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Enhanced custom token view for Aparsoft.

    Features:
    - Role-based authentication with appropriate context
    - Automatic profile validation and creation
    - Enhanced security and error handling
    - Dashboard routing based on user role
    """

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Request validation
        if not request.data.get("email") or not request.data.get("password"):
            return Response(
                {
                    "message": "Email and password are required.",
                    "code": "required_fields_missing",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-validate user exists and is active
        try:
            user = User.objects.get(email=request.data.get("email"))
            if not user.is_active:
                return Response(
                    {
                        "message": "Account is inactive. Please contact support.",
                        "code": "account_inactive",
                        "status": "error",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check role_status for suspended/blocked/inactive users
            if hasattr(user, "role_status") and user.role_status in [
                "suspended",
                "inactive",
                "blocked",
            ]:
                status_messages = {
                    "suspended": "Account is suspended. Please contact support.",
                    "inactive": "Account is inactive. Please contact support.",
                    "blocked": "Account is blocked. Please contact support.",
                }
                return Response(
                    {
                        "message": status_messages.get(
                            user.role_status,
                            "Account access is restricted. Please contact support.",
                        ),
                        "code": f"account_{user.role_status}",
                        "status": "error",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except User.DoesNotExist:
            # Don't reveal that the user doesn't exist
            pass

        try:
            # Use enhanced serializer with role-specific context
            serializer = self.get_serializer(data=request.data)

            if not serializer.is_valid():
                errors = serializer.errors

                # Handle specific authentication errors
                if "message" in errors:
                    error_message = str(errors["message"])
                    if "No active account found" in error_message:
                        return Response(
                            {
                                "message": "Invalid email or password.",
                                "code": "invalid_credentials",
                                "status": "error",
                            },
                            status=status.HTTP_401_UNAUTHORIZED,
                        )
                    elif "profile_not_found" in error_message:
                        return Response(
                            {
                                "message": "User profile incomplete. Please contact support.",
                                "code": "profile_incomplete",
                                "status": "error",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                if "non_field_errors" in errors:
                    return Response(
                        {
                            "message": "Authentication failed. Please check your credentials.",
                            "code": "authentication_failed",
                            "status": "error",
                        },
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                return Response(
                    {
                        "message": "Login validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Extract validated data and user
            data = serializer.validated_data
            user = serializer.user

            # DEBUG: Log user role information
            logger.info(f"User login - Email: {user.email}, Role: {user.role}, is_client: {user.is_client}")

            # AUTO-CREATE DocAPIClient if user is a client and doesn't have one
            if user.is_client:
                from documentintelligence.models import DocAPIClient
                from documentintelligence.services.docapi_initializer_service import get_docapi_initializer_service
                
                # Check if client record exists
                client_exists = DocAPIClient.objects.filter(user=user).exists()
                logger.info(f"DocAPIClient exists for {user.email}: {client_exists}")
                
                if not client_exists:
                    logger.info(f"Auto-creating DocAPIClient for user: {user.email}")
                    
                    try:
                        service = get_docapi_initializer_service()
                        
                        # Sanitize username for client_name
                        import re
                        sanitized_username = re.sub(r'[^a-zA-Z0-9_]', '_', user.username)
                        client_name = f"{sanitized_username}_{user.id}"
                        
                        result = service.create_client(
                            company_name=user.get_full_name() or user.email or "Individual",
                            client_name=client_name,
                            user_identifier=user,
                            plan_code="free",  # Start with free plan
                            description=f"Auto-created for {user.email}",
                            auto_generate_key=True,
                            activate_immediately=True,
                        )
                        
                        if result.success:
                            # CRITICAL: Save client and API key in transaction
                            with transaction.atomic():
                                result.client.save()
                                if result.api_key:
                                    result.api_key.save()
                                    logger.info(f"✓ API Key created: {result.api_key.key_prefix}...")
                                if result.webhook:
                                    result.webhook.save()
                            
                            logger.info(f"✓ DocAPIClient created successfully for {user.email}")
                            logger.info(f"  - Client ID: {result.client.id}")
                            logger.info(f"  - Client Name: {result.client.client_name}")
                            logger.info(f"  - Status: {result.client.status}")
                            logger.info(f"  - API Keys: {result.client.api_keys.count()}")
                        else:
                            logger.error(f"Failed to create DocAPIClient: {result.message}")
                    except Exception as e:
                        logger.error(f"Exception during DocAPIClient creation: {str(e)}", exc_info=True)
            else:
                logger.info(f"User {user.email} is not a client (role: {user.role}), skipping DocAPIClient creation")

            # Update user's login count and last active
            user.login_count += 1
            user.last_active = timezone.now()
            user.save(update_fields=["login_count", "last_active"])

            # Enhanced user data with role-specific context
            enhanced_user_data = self._get_enhanced_login_response(user, data)

            # Create response with enhanced data
            response = Response(
                {
                    "message": "Login successful",
                    "status": "success",
                    "data": enhanced_user_data,
                },
                status=status.HTTP_200_OK,
            )

            # Set secure HTTP-only cookies
            self._set_auth_cookies(response, data)

            logger.info(f"Successful login for {user.role}: {user.email}")
            return response

        except AuthenticationFailed as auth_error:
            logger.debug(f"Authentication failed: {str(auth_error)}")
            return Response(
                {
                    "message": "Invalid email or password.",
                    "code": "invalid_credentials",
                    "status": "error",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except ValidationError as validation_error:
            logger.info(f"Validation error: {str(validation_error)}")
            return Response(
                {
                    "message": str(validation_error),
                    "code": "validation_error",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error("Unexpected login error:", exc_info=True)
            return Response(
                {
                    "message": "An error occurred during login. Please try again.",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_enhanced_login_response(
        self, user, token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create enhanced login response with role-specific context."""

        # Base user data from serializer
        user_data = token_data.get("user", {})

        # Add organization context if applicable
        organization_data = None
        if user.client_organization:
            organization_data = {
                "id": user.client_organization.id,
                "name": user.client_organization.name,
                "organization_type": user.client_organization.organization_type,
                "subscription_tier": user.subscription_tier,
            }

        # Add role-specific data and dashboard routing
        role_data = {}
        dashboard_route = "/dashboard"

        if user.is_developer and hasattr(user, "developer_profile"):
            developer = user.developer_profile
            role_data = {
                "experience_level": developer.experience_level,
                "technical_expertise": developer.get_skills_summary(),
                "availability": developer.is_available,
                "utilization_rate": developer.utilization_rate,
                "team": developer.team.name if developer.team else None,
            }
            dashboard_route = "/platform/developer"

        elif user.is_client and hasattr(user, "client_profile"):
            client = user.client_profile
            role_data = {
                "client_type": client.client_type,
                "client_status": client.client_status,
                "industry_sector": client.industry_sector,
                "active_projects_count": client.active_projects_count,
                "account_manager": (
                    client.account_manager.full_name if client.account_manager else None
                ),
                "subscription_tier": user.subscription_tier,
                "onboarding_complete": client.client_status == "active",
            }
            dashboard_route = "/platform/client"

        elif user.is_project_manager and hasattr(user, "project_manager_profile"):
            pm = user.project_manager_profile
            role_data = {
                "experience_level": pm.experience_level,
                "primary_methodology": pm.primary_methodology,
                "active_projects_count": pm.active_projects_count,
                "utilization_percentage": pm.utilization_percentage,
            }
            dashboard_route = "/dashboard/project-manager"

        elif user.is_account_manager and hasattr(user, "account_manager_profile"):
            am = user.account_manager_profile
            role_data = {
                "experience_level": am.experience_level,
                "sales_focus": am.sales_focus,
                "active_clients_count": am.active_clients_count,
                "client_satisfaction_score": float(am.client_satisfaction_score),
                "pipeline_value": float(am.pipeline_value),
            }
            dashboard_route = "/dashboard/account-manager"

        elif user.role == "admin":
            role_data = {
                "admin_permissions": [
                    "manage_users",
                    "view_system_analytics",
                    "manage_settings",
                    "billing_management",
                    "user_creation",
                    "system_configuration",
                    "view_all_projects",
                    "view_all_clients",
                ],
                "system_access": "full",
                "managed_resources": [
                    "users",
                    "projects",
                    "clients",
                    "billing",
                    "system",
                ],
            }
            dashboard_route = "/platform/admin"

        # Get user permissions
        permissions = self._get_user_permissions(user)

        # Check for profile completion requirements
        profile_completion = self._check_profile_completion(user)

        return {
            "tokens": {
                "access": token_data["access"],
                "refresh": token_data["refresh"],
            },
            "user": {
                **user_data,
                "role_data": role_data,
                "permissions": permissions,
                "profile_completion": profile_completion,
            },
            "organization": organization_data,
            "navigation": {
                "dashboard_route": dashboard_route,
                "next_action": self._get_next_action(user),
            },
            "session_info": {
                "login_count": user.login_count,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "session_expires": (
                    timezone.now() + timezone.timedelta(hours=1)
                ).isoformat(),
            },
        }

    def _set_auth_cookies(self, response: Response, token_data: Dict[str, Any]) -> None:
        """Set secure HTTP-only authentication cookies."""
        cookie_settings = {
            "httponly": True,
            "samesite": "Lax",
            "secure": not settings.DEBUG,
            "path": "/",
        }

        # Set refresh token (7 days)
        response.set_cookie(
            "refresh_token",
            token_data["refresh"],
            max_age=7 * 24 * 60 * 60,
            **cookie_settings,
        )

        # Set access token (1 hour)
        response.set_cookie(
            "access_token", token_data["access"], max_age=60 * 60, **cookie_settings
        )

        # Set auth state (readable by JS)
        response.set_cookie(
            "auth_state",
            "authenticated",
            httponly=False,
            max_age=7 * 24 * 60 * 60,
            **{k: v for k, v in cookie_settings.items() if k != "httponly"},
        )

    def _get_user_permissions(self, user) -> list:
        """Get user permissions based on role and context."""
        base_permissions = ["view_profile", "update_profile"]

        if user.is_developer:
            base_permissions.extend(
                [
                    "view_assigned_tasks",
                    "update_task_status",
                    "view_project_details",
                    "track_time",
                    "submit_code",
                    "view_team_members",
                ]
            )

            # Senior developers get additional permissions
            if user.is_senior_developer:
                base_permissions.extend(
                    ["review_code", "assign_tasks", "view_project_analytics"]
                )

        elif user.is_client:
            base_permissions.extend(
                [
                    "view_projects",
                    "view_project_status",
                    "create_support_tickets",
                    "approve_deliverables",
                    "access_resources",
                    "view_invoices",
                ]
            )

            # Business and enterprise clients get additional permissions
            if user.is_business or user.is_enterprise:
                base_permissions.extend(
                    ["view_detailed_analytics", "api_access", "priority_support"]
                )

        elif user.is_project_manager:
            base_permissions.extend(
                [
                    "create_projects",
                    "manage_team",
                    "assign_tasks",
                    "view_analytics",
                    "generate_reports",
                    "manage_client_communication",
                    "update_project_status",
                    "manage_resources",
                ]
            )

        elif user.is_account_manager:
            base_permissions.extend(
                [
                    "manage_clients",
                    "view_sales_pipeline",
                    "create_opportunities",
                    "view_client_analytics",
                    "generate_quotes",
                    "manage_contracts",
                ]
            )

        elif user.role == "admin":
            base_permissions.extend(
                [
                    "manage_users",
                    "view_system_analytics",
                    "manage_settings",
                    "billing_management",
                    "user_creation",
                    "system_configuration",
                    "view_all_projects",
                    "view_all_clients",
                ]
            )

        elif user.is_superuser:
            base_permissions.append("full_access")

        return base_permissions

    def _check_profile_completion(self, user) -> Dict[str, Any]:
        """Check if user profile is complete and what steps are needed."""
        completion_status = {
            "is_complete": True,
            "missing_fields": [],
            "next_steps": [],
        }

        # Check basic profile fields
        if not user.first_name or not user.last_name:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("name")
            completion_status["next_steps"].append("Complete your name")

        # Check email verification
        if not user.email_verified:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("email_verification")
            completion_status["next_steps"].append("Verify your email address")

        # Check contact information
        try:
            contact = user.contact
            if not contact.country or not contact.city:
                completion_status["is_complete"] = False
                completion_status["missing_fields"].append("location")
                completion_status["next_steps"].append("Add your location")
        except UserContact.DoesNotExist:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("contact")
            completion_status["next_steps"].append("Complete contact information")

        # Role-specific checks
        if user.is_developer and hasattr(user, "developer_profile"):
            developer = user.developer_profile
            if not developer.technical_expertise:
                completion_status["missing_fields"].append("technical_skills")
                completion_status["next_steps"].append("Add your technical skills")
                completion_status["is_complete"] = False

            if not developer.programming_languages:
                completion_status["missing_fields"].append("programming_languages")
                completion_status["next_steps"].append("Add your programming languages")
                completion_status["is_complete"] = False

        elif user.is_client and hasattr(user, "client_profile"):
            client = user.client_profile
            if client.client_status == "onboarding":
                completion_status["next_steps"].append("Complete onboarding process")
                completion_status["is_complete"] = False

            if not client.industry_sector:
                completion_status["missing_fields"].append("industry_sector")
                completion_status["next_steps"].append("Set your industry sector")
                completion_status["is_complete"] = False

        elif user.is_project_manager and hasattr(user, "project_manager_profile"):
            pm = user.project_manager_profile
            if not pm.methodologies:
                completion_status["missing_fields"].append("methodologies")
                completion_status["next_steps"].append(
                    "Add your project management methodologies"
                )
                completion_status["is_complete"] = False

            if not pm.domain_expertise:
                completion_status["missing_fields"].append("domain_expertise")
                completion_status["next_steps"].append("Add your domain expertise")
                completion_status["is_complete"] = False

        elif user.is_account_manager and hasattr(user, "account_manager_profile"):
            am = user.account_manager_profile
            if not am.industry_specializations:
                completion_status["missing_fields"].append("industry_specializations")
                completion_status["next_steps"].append(
                    "Add your industry specializations"
                )
                completion_status["is_complete"] = False

            if not am.solution_expertise:
                completion_status["missing_fields"].append("solution_expertise")
                completion_status["next_steps"].append("Add your solution expertise")
                completion_status["is_complete"] = False

        return completion_status

    def _get_next_action(self, user) -> str:
        """Determine the next recommended action for the user."""
        if not user.email_verified:
            return "verify_email"

        if user.is_developer:
            if hasattr(user, "developer_profile"):
                developer = user.developer_profile
                if not developer.team:
                    return "join_team"
                elif (
                    developer.project_history is None
                    or len(developer.project_history) == 0
                ):
                    return "view_available_projects"
            return "view_tasks"

        elif user.is_client:
            if hasattr(user, "client_profile"):
                client = user.client_profile
                if client.client_status == "onboarding":
                    return "complete_onboarding"
                elif client.active_projects_count == 0:
                    return "explore_services"
            return "view_projects"

        elif user.is_project_manager:
            if hasattr(user, "project_manager_profile"):
                pm = user.project_manager_profile
                if pm.active_projects_count == 0:
                    return "create_project"
            return "manage_projects"

        elif user.is_account_manager:
            if hasattr(user, "account_manager_profile"):
                am = user.account_manager_profile
                if am.active_clients_count == 0:
                    return "add_clients"
                elif am.opportunities is None or len(am.opportunities) == 0:
                    return "create_opportunity"
            return "manage_clients"

        elif user.role == "admin":
            return "system_overview"

        return "complete_profile"


class LogoutView(APIView):
    """
    Enhanced logout view with comprehensive session cleanup.

    Features:
    - Graceful handling of expired/invalid tokens
    - Complete cookie cleanup
    - Session blacklisting
    - Multi-device logout support
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh") or request.data.get(
                "refresh_token"
            )
            all_devices = request.data.get("all_devices", False)

            # Handle logout with invalid/expired token
            if request.auth is None and request.user is None:
                logger.info("Processing logout with expired token")
                return self._create_logout_response(
                    message="Session expired, cookies cleared",
                    code="logout_expired_token",
                )

            # Handle logout without refresh token
            if not refresh_token:
                logger.warning("No refresh token provided in logout")
                if hasattr(request, "user") and request.user.is_authenticated:
                    request.user.update_last_active()
                return self._create_logout_response(
                    message="Logged out successfully", code="logout_without_token"
                )

            # Validate and blacklist token
            try:
                token = RefreshToken(refresh_token)

                # Verify token belongs to current user
                if (
                    hasattr(request, "user")
                    and request.user.is_authenticated
                    and token.payload.get("user_id") != request.user.id
                ):
                    logger.warning(f"Token user mismatch during logout")
                    return self._create_logout_response(
                        message="Invalid token, but logged out", code="token_mismatch"
                    )

                # Blacklist the token
                token.blacklist()

                # Update user's last active
                if hasattr(request, "user") and request.user.is_authenticated:
                    request.user.update_last_active()

                # Handle multi-device logout
                if (
                    all_devices
                    and hasattr(request, "user")
                    and request.user.is_authenticated
                ):
                    logger.info(f"Logging out all devices for user: {request.user.id}")
                    OutstandingToken.objects.filter(user=request.user).delete()

                logger.info(
                    f"Successful logout for user: {getattr(request.user, 'email', 'Unknown')}"
                )
                return self._create_logout_response(
                    message="Successfully logged out", code="logout_success"
                )

            except Exception as token_error:
                logger.warning(
                    f"Token validation error during logout: {str(token_error)}"
                )
                return self._create_logout_response(
                    message="Invalid token, but logged out", code="invalid_token"
                )

        except Exception as e:
            logger.error(f"Unexpected logout error: {str(e)}", exc_info=True)
            return self._create_logout_response(
                message="Error occurred, but logged out", code="error_but_logged_out"
            )

    def _create_logout_response(self, message: str, code: str) -> Response:
        """Create logout response with cookie cleanup."""
        response = Response(
            {"message": message, "code": code, "status": "success"},
            status=status.HTTP_200_OK,
        )

        # Clear all authentication cookies
        cookies_to_clear = ["auth_state", "access_token", "refresh_token", "csrftoken"]
        for cookie in cookies_to_clear:
            response.delete_cookie(cookie, path="/")

        return response
