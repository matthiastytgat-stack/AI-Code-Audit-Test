"""
User API Key Model - Store encrypted API keys for AI providers.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
from cryptography.fernet import Fernet
from django.conf import settings as django_settings
import os


class UserAPIKey(TimestampedModel):
    """
    Store encrypted user API keys for various AI providers.

    Allows users to use their own API keys instead of platform credits.
    Keys are encrypted at rest for security.
    """

    # User association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text=_("User who owns this API key"),
    )

    # Provider information
    provider = models.CharField(
        max_length=50,
        choices=[
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic (Claude)"),
            ("google", "Google AI"),
            ("cohere", "Cohere"),
            ("huggingface", "HuggingFace"),
            ("azure", "Azure OpenAI"),
            ("custom", "Custom Provider"),
        ],
        help_text=_("AI provider for this key"),
    )

    provider_display_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Custom display name for provider"),
    )

    # Encrypted key
    encrypted_key = models.BinaryField(
        help_text=_("Encrypted API key (stored securely)")
    )

    # Key metadata
    key_name = models.CharField(
        max_length=255, help_text=_("User-friendly name for this key")
    )

    key_prefix = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_("First few characters of key (for identification)"),
    )

    # Status
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this key is active and usable")
    )

    is_default = models.BooleanField(
        default=False, help_text=_("Whether this is the default key for this provider")
    )

    # Validation
    is_validated = models.BooleanField(
        default=False, help_text=_("Whether key has been validated with provider")
    )

    last_validated_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When key was last validated")
    )

    validation_error = models.TextField(
        blank=True, null=True, help_text=_("Error message from last validation attempt")
    )

    # Usage tracking
    usage_count = models.IntegerField(
        default=0, help_text=_("Number of times this key has been used")
    )

    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this key was last used")
    )

    total_tokens_used = models.BigIntegerField(
        default=0, help_text=_("Total tokens used with this key")
    )

    # Rate limiting and quotas
    daily_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Daily usage limit (in tokens, null = unlimited)"),
    )

    monthly_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Monthly usage limit (in tokens, null = unlimited)"),
    )

    # Additional configuration
    custom_config = models.JSONField(
        default=dict, blank=True, help_text=_("Provider-specific configuration")
    )

    class Meta:
        verbose_name = _("User API Key")
        verbose_name_plural = _("User API Keys")
        ordering = ["-is_default", "-last_used_at"]
        unique_together = ["user", "provider", "key_name"]
        indexes = [
            models.Index(fields=["user", "provider"], name="apikey_user_provider_idx"),
            models.Index(fields=["user", "is_active"], name="apikey_user_active_idx"),
            models.Index(fields=["is_default"], name="apikey_default_idx"),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.provider} ({self.key_name})"

    @staticmethod
    def get_encryption_key():
        """Get or create encryption key."""
        # In production, store this in environment variable or secrets manager
        key = getattr(django_settings, "API_KEY_ENCRYPTION_KEY", None)

        if not key:
            # Generate a key (do this once and save it)
            key = Fernet.generate_key()
            # In production: save this key securely!

        return key

    def encrypt_api_key(self, api_key):
        """Encrypt API key before storage."""
        encryption_key = self.get_encryption_key()
        fernet = Fernet(encryption_key)

        # Store first few chars as prefix
        self.key_prefix = api_key[:8] if len(api_key) >= 8 else api_key[:4]

        # Encrypt the full key
        self.encrypted_key = fernet.encrypt(api_key.encode())

    def decrypt_api_key(self):
        """Decrypt API key for use."""
        encryption_key = self.get_encryption_key()
        fernet = Fernet(encryption_key)

        decrypted = fernet.decrypt(self.encrypted_key)
        return decrypted.decode()

    def validate_key(self):
        """
        Validate API key with provider.

        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        from django.utils import timezone

        try:
            api_key = self.decrypt_api_key()

            # Validate based on provider
            if self.provider == "openai":
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                # Test with minimal request
                client.models.list()

            elif self.provider == "anthropic":
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                # Test request
                client.models.list()

            # Add more providers as needed

            # Mark as validated
            self.is_validated = True
            self.last_validated_at = timezone.now()
            self.validation_error = None
            self.save(
                update_fields=["is_validated", "last_validated_at", "validation_error"]
            )

            return {"valid": True, "error": None}

        except Exception as e:
            self.is_validated = False
            self.validation_error = str(e)
            self.save(update_fields=["is_validated", "validation_error"])

            return {"valid": False, "error": str(e)}

    def increment_usage(self, tokens_used=0):
        """Track key usage."""
        from django.utils import timezone

        self.usage_count += 1
        self.total_tokens_used += tokens_used
        self.last_used_at = timezone.now()

        self.save(update_fields=["usage_count", "total_tokens_used", "last_used_at"])

    def check_limits(self, tokens_to_use=0):
        """
        Check if usage would exceed limits.

        Returns:
            dict: {'allowed': bool, 'reason': str}
        """
        from django.utils import timezone
        from datetime import timedelta

        # Check daily limit
        if self.daily_limit:
            today_start = timezone.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            from .token_usage import TokenUsage

            today_usage = (
                TokenUsage.objects.filter(
                    user=self.user,
                    created_at__gte=today_start,
                    metadata__api_key_id=self.id,
                ).aggregate(total=models.Sum("total_tokens"))["total"]
                or 0
            )

            if today_usage + tokens_to_use > self.daily_limit:
                return {
                    "allowed": False,
                    "reason": f"Daily limit exceeded ({self.daily_limit} tokens)",
                }

        # Check monthly limit
        if self.monthly_limit:
            month_start = timezone.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

            from .token_usage import TokenUsage

            month_usage = (
                TokenUsage.objects.filter(
                    user=self.user,
                    created_at__gte=month_start,
                    metadata__api_key_id=self.id,
                ).aggregate(total=models.Sum("total_tokens"))["total"]
                or 0
            )

            if month_usage + tokens_to_use > self.monthly_limit:
                return {
                    "allowed": False,
                    "reason": f"Monthly limit exceeded ({self.monthly_limit} tokens)",
                }

        return {"allowed": True, "reason": "Within limits"}

    @classmethod
    def get_default_key(cls, user, provider):
        """Get default key for user and provider."""
        return cls.objects.filter(
            user=user, provider=provider, is_active=True, is_default=True
        ).first()
