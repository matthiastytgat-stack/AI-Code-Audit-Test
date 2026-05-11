# /home/ram/aparsoft/backend/apps/accounts/api/views/auth_password_reset_views.py

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
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
import logging
from rest_framework.throttling import AnonRateThrottle
from decouple import config


logger = logging.getLogger(__name__)
User = get_user_model()


class PasswordResetView(APIView):
    """
    Enhanced password reset view for Aparsoft.
    Handles password reset requests with comprehensive security.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {
                    "message": "Email address is required",
                    "code": "email_required",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)

            # Generate password reset token and URL
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Create password reset URL for frontend
            domain = config("DOMAIN_NAME", "localhost")
            if domain == "localhost":
                frontend_url = "http://localhost:3000"
            else:
                frontend_url = f"https://{domain}"
            reset_url = f"{frontend_url}/auth/reset-password?uid={uid}&token={token}"

            # TODO: Send email with reset_url
            # This would typically use a task queue like Celery
            # send_password_reset_email_task.delay(user.id, reset_url)

            logger.info(f"Password reset requested for: {email}")

            return Response(
                {
                    "message": "Password reset instructions sent to your email",
                    "status": "success",
                },
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            # For security, don't reveal if email exists or not
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return Response(
                {
                    "message": "If an account exists with this email, reset instructions will be sent",
                    "status": "success",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Password reset error for {email}: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Error processing password reset request",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PasswordResetConfirmView(APIView):
    """
    Password reset confirmation view.
    Handles the actual password reset when user clicks the email link.
    """

    permission_classes = [AllowAny]  # Public endpoint - accessed via email link
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Validate required fields
        if not all([uid, token, new_password, confirm_password]):
            return Response(
                {
                    "message": "Missing required fields",
                    "code": "missing_fields",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check password match
        if new_password != confirm_password:
            return Response(
                {
                    "message": "Passwords do not match",
                    "code": "password_mismatch",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate password strength (basic)
        if len(new_password) < 8:
            return Response(
                {
                    "message": "Password must be at least 8 characters long",
                    "code": "password_too_short",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Decode user ID
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response(
                    {
                        "message": "Invalid reset link",
                        "code": "invalid_link",
                        "status": "error",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if token is valid
            if not default_token_generator.check_token(user, token):
                return Response(
                    {
                        "message": "Invalid or expired reset link",
                        "code": "invalid_token",
                        "status": "error",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update password
            user.set_password(new_password)
            user.save()

            # Log password reset
            logger.info(f"Password reset successful for: {user.email}")

            # TODO: Send confirmation email
            # send_password_reset_confirmation_email_task.delay(user.id)

            return Response(
                {"message": "Password reset successful", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Error resetting password",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """Validate reset token without resetting password."""
        uid = request.GET.get("uid")
        token = request.GET.get("token")

        if not uid or not token:
            return Response(
                {
                    "message": "Missing reset parameters",
                    "code": "missing_params",
                    "status": "error",
                    "valid": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Decode user ID
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response(
                    {
                        "message": "Invalid reset link",
                        "code": "invalid_link",
                        "status": "error",
                        "valid": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if token is valid
            is_valid = default_token_generator.check_token(user, token)

            return Response(
                {
                    "message": (
                        "Token validated" if is_valid else "Invalid or expired token"
                    ),
                    "status": "success" if is_valid else "error",
                    "valid": is_valid,
                    "user_email": user.email if is_valid else None,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Token validation error: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Error validating token",
                    "code": "server_error",
                    "status": "error",
                    "valid": False,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PasswordChangeView(APIView):
    """
    Password change view for authenticated users.
    Allows users to change their password by providing current password.
    """

    permission_classes = [IsAuthenticated]  # Requires authentication

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        # Validate required fields
        if not current_password or not new_password:
            return Response(
                {
                    "message": "Current password and new password are required",
                    "code": "missing_fields",
                    "status": "error",
                    "errors": {
                        "current_password": (
                            "Current password is required"
                            if not current_password
                            else None
                        ),
                        "new_password": (
                            "New password is required" if not new_password else None
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate current password
        user = request.user
        if not user.check_password(current_password):
            return Response(
                {
                    "message": "Current password is incorrect",
                    "code": "invalid_current_password",
                    "status": "error",
                    "errors": {"current_password": "Current password is incorrect"},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate new password strength
        if len(new_password) < 8:
            return Response(
                {
                    "message": "New password must be at least 8 characters long",
                    "code": "password_too_short",
                    "status": "error",
                    "errors": {
                        "new_password": "Password must be at least 8 characters long"
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if new password is different from current
        if current_password == new_password:
            return Response(
                {
                    "message": "New password must be different from current password",
                    "code": "same_password",
                    "status": "error",
                    "errors": {
                        "new_password": "New password must be different from current password"
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Update password
            user.set_password(new_password)
            user.save()

            # Log password change
            logger.info(f"Password changed successfully for: {user.email}")

            return Response(
                {"message": "Password changed successfully", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(
                f"Password change error for {user.email}: {str(e)}", exc_info=True
            )
            return Response(
                {
                    "message": "Error changing password",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EmailVerificationView(APIView):
    """
    Enhanced email verification view for Aparsoft.
    Handles email verification requests and confirmations.
    """

    permission_classes = [AllowAny]  # Default - overridden in get_permissions()

    def get_permissions(self):
        """
        Override to require authentication only for POST requests (sending verification email).
        GET requests should be allowed for unauthenticated users clicking email links.
        """
        if self.request.method == "POST":
            # POST requires authentication to send verification email
            return [IsAuthenticated()]
        # GET allows public access for email verification links
        return [AllowAny()]

    def post(self, request):
        """Request email verification."""
        try:
            user = request.user

            logger.info(
                f"Email verification requested - Authenticated user: {user.id if user.is_authenticated else 'Anonymous'} - {user.email if user.is_authenticated else 'No email'}"
            )

            if user.email_verified:
                return Response(
                    {"message": "Email is already verified", "status": "info"},
                    status=status.HTTP_200_OK,
                )

            # Generate email verification token and URL
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Create email verification URL for frontend
            domain = config("DOMAIN_NAME", "localhost")
            if domain == "localhost":
                frontend_url = "http://localhost:3000"
            else:
                frontend_url = f"https://{domain}"
            verification_url = (
                f"{frontend_url}/auth/verify-email?uid={uid}&token={token}"
            )

            # TODO: Send email with verification_url
            # This would typically use a task queue like Celery
            # send_email_verification_task.delay(user.id, verification_url)

            logger.info(f"Email verification requested for: {user.email}")

            return Response(
                {"message": "Verification email sent", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Email verification request error: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Error sending verification email",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """Verify email with token."""
        token = request.GET.get("token")
        uid = request.GET.get("uid")

        if not token:
            return Response(
                {
                    "message": "Verification token is required",
                    "code": "token_required",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # If uid is provided, validate it (for email links)
            if uid:
                try:
                    user_id = force_str(urlsafe_base64_decode(uid))
                    user = User.objects.get(pk=user_id)
                except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                    return Response(
                        {
                            "message": "Invalid verification link",
                            "code": "invalid_link",
                            "status": "error",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check if token is valid for this user
                if not default_token_generator.check_token(user, token):
                    return Response(
                        {
                            "message": "Invalid or expired verification link",
                            "code": "invalid_token",
                            "status": "error",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                # No uid provided - this is an error for email verification
                return Response(
                    {
                        "message": "User identifier required for email verification",
                        "code": "uid_required",
                        "status": "error",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if email is already verified
            if user.email_verified:
                return Response(
                    {"message": "Email is already verified", "status": "success"},
                    status=status.HTTP_200_OK,
                )

            # Mark email as verified
            user.email_verified = True
            user.save(update_fields=["email_verified"])

            logger.info(f"Email verified successfully for: {user.email}")

            return Response(
                {"message": "Email verified successfully", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Email verification error: {str(e)}", exc_info=True)
            return Response(
                {
                    "message": "Error verifying email",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
