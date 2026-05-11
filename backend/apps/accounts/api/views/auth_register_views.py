# /home/ram/aparsoft/backend/apps/accounts/api/views/auth_register_views.py

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
from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import logging
import re
from rest_framework.throttling import AnonRateThrottle
from typing import Dict, Any

# Import enhanced serializers
from ..serializers import (
    RegisterSerializer,
)

# Profile creation is now handled by signals
# No need to import profile models here

logger = logging.getLogger(__name__)
User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class RegisterView(APIView):
    """
    Enhanced registration view for Aparsoft.

    Features:
    - Automatic profile creation based on user role
    - Enhanced error handling and validation
    - Integration with Aparsoft workflow
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        logger.info(f"Registration attempt for role: {request.data.get('role')}")

        try:
            # Enhanced validation for registration data
            validation_result = self._validate_registration_data(request.data)
            if not validation_result["is_valid"]:
                return Response(
                    {
                        "message": validation_result["message"],
                        "code": validation_result["code"],
                        "status": "error",
                        "errors": validation_result.get("errors", {}),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create user with enhanced serializer
            serializer = RegisterSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                logger.info(f"Registration validation errors: {serializer.errors}")
                return Response(
                    {
                        "message": "Registration validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Save user (signals will automatically create the profile)
            user = serializer.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            # Create enhanced response
            response_data = {
                "message": f"{user.role.title()} registration successful",
                "status": "success",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "subscription_tier": user.subscription_tier,
                    "email_verified": user.email_verified,
                    "profile_created": user.role,  # Profile created by signals
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                "organization": None,
                "next_steps": [
                    "Verify your email address",
                    "Complete your profile",
                    "Explore the platform",
                ],
            }

            # Add organization context if applicable
            if user.client_organization:
                response_data["organization"] = {
                    "id": user.client_organization.id,
                    "name": user.client_organization.name,
                }
                response_data["next_steps"].insert(
                    1, "Set up your organization profile"
                )

            # Add role-specific next steps based on primary focus (admin, developer, client)
            if user.role == "admin":
                response_data["next_steps"].extend(
                    ["Set up system configuration", "Manage user roles"]
                )
            elif user.is_developer or user.role in ["developer", "senior_developer"]:
                response_data["next_steps"].extend(
                    ["Add your technical skills", "Join a development team"]
                )
            elif user.is_client or user.role == "client":
                response_data["next_steps"].extend(
                    ["Complete company profile", "Explore available services"]
                )
            elif user.is_project_manager:
                response_data["next_steps"].append("Create your first project")
            elif user.is_account_manager:
                response_data["next_steps"].append("Add your first client")

            logger.info(f"Successful registration for {user.role}: {user.email}")
            return Response(response_data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.info(f"Custom validation error: {str(e)}")
            return Response(
                {"message": str(e), "code": "validation_error", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error("Registration error:", exc_info=True)
            return Response(
                {
                    "message": "An error occurred during registration. Please try again.",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_registration_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate registration data with specific checks."""

        # Check required fields
        required_fields = [
            "email",
            "password1",
            "password2",
            "first_name",
            "last_name",
            "role",
        ]
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return {
                "is_valid": False,
                "message": f'Missing required fields: {", ".join(missing_fields)}',
                "code": "missing_required_fields",
                "errors": {
                    field: ["This field is required."] for field in missing_fields
                },
            }

        # Validate role - For normal registration, restrict to client only
        role = data.get("role")
        valid_roles = [
            "developer",
            "senior_developer",
            "project_manager",
            "client",
            "account_manager",
            "admin",
        ]
        if role not in valid_roles:
            return {
                "is_valid": False,
                "message": f'Invalid role. Must be one of: {", ".join(valid_roles)}',
                "code": "invalid_role",
            }

        # Check if this is normal client registration (no invitation token)
        invitation_token = data.get("invitation_token")
        if not invitation_token:
            # For public registration, only allow client role
            if role != "client":
                return {
                    "is_valid": False,
                    "message": "Direct registration is only available for clients. Other roles require invitation.",
                    "code": "direct_registration_restricted",
                }

        # Role-specific validation
        if role in ["developer", "senior_developer"]:
            # Validate developer experience level
            experience_level = data.get("experience_level")
            if experience_level:
                valid_exp_levels = ["junior", "mid", "senior", "lead", "architect"]
                if experience_level not in valid_exp_levels:
                    return {
                        "is_valid": False,
                        "message": f'Invalid experience level. Must be one of: {", ".join(valid_exp_levels)}',
                        "code": "invalid_experience_level",
                    }

        elif role == "client":
            # Validate client type
            client_type = data.get("client_type")
            if client_type:
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
                if client_type not in valid_client_types:
                    return {
                        "is_valid": False,
                        "message": f'Invalid client type. Must be one of: {", ".join(valid_client_types)}',
                        "code": "invalid_client_type",
                    }

        # Phone number validation (if provided)
        phone_number = data.get("phone_number")
        if phone_number and phone_number.strip():  # Only validate if phone number is provided
            phone_validation = self._validate_indian_phone_number(phone_number)
            if not phone_validation["is_valid"]:
                return phone_validation

        # Email uniqueness check
        if User.objects.filter(email=data.get("email")).exists():
            return {
                "is_valid": False,
                "message": "User with this email already exists",
                "code": "email_already_exists",
            }

        return {"is_valid": True}

    def _validate_indian_phone_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Validate Indian phone number format.
        
        This method can be easily modified to support different validation rules
        or extended to support other countries in the future.
        
        Valid Indian phone number formats:
        - +91 9876543210
        - +91-9876-543210
        - +91 9876 543210
        - 9876543210
        - +919876543210
        
        Rules:
        - Must be exactly 10 digits after country code
        - Must start with 6, 7, 8, or 9 (valid Indian mobile prefixes)
        - Country code +91 is optional but if present, must be correct
        """
        if not phone_number:
            return {"is_valid": True}  # Empty phone is handled by required field validation
        
        try:
            # Clean the phone number - remove spaces, hyphens, and plus signs
            cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone_number.strip())
            
            # Handle country code if present
            if cleaned_phone.startswith('91'):
                # Remove country code
                cleaned_phone = cleaned_phone[2:]
            
            # Validate cleaned phone number
            if not cleaned_phone.isdigit():
                return {
                    "is_valid": False,
                    "message": "Phone number must contain only digits",
                    "code": "invalid_phone_format",
                    "errors": {
                        "phone_number": ["Phone number must contain only digits and valid formatting"]
                    }
                }
            
            # Check length - must be exactly 10 digits
            if len(cleaned_phone) != 10:
                return {
                    "is_valid": False,
                    "message": f"Indian phone number must be exactly 10 digits, got {len(cleaned_phone)}",
                    "code": "invalid_phone_length",
                    "errors": {
                        "phone_number": [f"Phone number must be exactly 10 digits, got {len(cleaned_phone)} digits"]
                    }
                }
            
            # Check first digit - must be 6, 7, 8, or 9 (valid Indian mobile prefixes)
            first_digit = cleaned_phone[0]
            if first_digit not in ['6', '7', '8', '9']:
                return {
                    "is_valid": False,
                    "message": f"Indian mobile numbers must start with 6, 7, 8, or 9, got {first_digit}",
                    "code": "invalid_phone_prefix",
                    "errors": {
                        "phone_number": [f"Mobile number must start with 6, 7, 8, or 9, got {first_digit}"]
                    }
                }
            
            # Additional validation - check for obviously invalid patterns
            # All same digits (e.g., 9999999999)
            if len(set(cleaned_phone)) == 1:
                return {
                    "is_valid": False,
                    "message": "Phone number cannot have all identical digits",
                    "code": "invalid_phone_pattern",
                    "errors": {
                        "phone_number": ["Phone number cannot have all identical digits"]
                    }
                }
            
            # Sequential digits (e.g., 1234567890) - only reject truly sequential patterns
            if cleaned_phone in ['1234567890', '0123456789']:
                return {
                    "is_valid": False,
                    "message": "Phone number cannot be a sequential pattern",
                    "code": "invalid_phone_pattern",
                    "errors": {
                        "phone_number": ["Phone number cannot be a sequential pattern"]
                    }
                }
            
            return {"is_valid": True}
            
        except Exception as e:
            logger.error(f"Phone validation error: {str(e)}")
            return {
                "is_valid": False,
                "message": "Error validating phone number format",
                "code": "phone_validation_error",
                "errors": {
                    "phone_number": ["Error validating phone number format"]
                }
            }

    # Profile creation is now handled by signals in user_creation_signals.py
    # This eliminates duplicate profile creation and ensures consistency


@method_decorator(ensure_csrf_cookie, name="dispatch")
class OrganizationRegisterView(APIView):
    """
    Special registration view for creating organization-associated users.
    This is typically used during organization onboarding.
    """

    permission_classes = [AllowAny]  # May need to restrict this in production
    throttle_classes = [AnonRateThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            # Validate organization exists
            organization_id = request.data.get("organization_id")
            if not organization_id:
                return Response(
                    {
                        "message": "Organization ID is required",
                        "code": "organization_id_required",
                        "status": "error",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            organization = get_object_or_404(
                "customers.Organization", id=organization_id
            )

            # Create user data
            user_data = {**request.data, "client_organization": organization_id}

            # Use regular registration logic
            serializer = RegisterSerializer(
                data=user_data, context={"request": request}
            )

            if not serializer.is_valid():
                return Response(
                    {
                        "message": "Validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create user
            user = serializer.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Organization user created successfully",
                    "status": "success",
                    "data": {
                        "user": {
                            "id": user.id,
                            "email": user.email,
                            "name": user.full_name,
                            "role": user.role,
                        },
                        "organization": {
                            "id": organization.id,
                            "name": organization.name,
                        },
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error("Organization user registration error:", exc_info=True)
            return Response(
                {
                    "message": "Error creating organization user",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    """Enhanced CSRF token view with proper headers."""

    permission_classes = [AllowAny]

    def get(self, request):
        # Ensure CSRF token is set and get it
        from django.middleware.csrf import get_token

        csrf_token = get_token(request)
        response = JsonResponse(
            {
                "message": "CSRF cookie set successfully",
                "status": "success",
                "csrfToken": csrf_token,
            }
        )

        # Set cache control headers
        response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        # Add CORS headers if needed
        if settings.DEBUG:
            response["Access-Control-Allow-Origin"] = "http://localhost:3000"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = (
                "Content-Type, X-CSRFToken, Authorization"
            )

        response["X-CSRF-Token-Status"] = "Set"

        return response
