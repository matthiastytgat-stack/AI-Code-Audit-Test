"""
User Tool Model - Custom tools/functions users can enable.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class UserTool(TimestampedModel):
    """
    Track which tools/functions users have enabled.

    Tools are defined in code but users can enable/disable them
    and configure their settings.
    """

    # User association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enabled_tools",
        help_text=_("User who configured this tool"),
    )

    # Tool identification
    tool_name = models.CharField(
        max_length=100,
        help_text=_('Internal name of the tool (e.g., "web_search", "code_executor")'),
    )

    tool_display_name = models.CharField(
        max_length=255, help_text=_("Human-readable tool name")
    )

    # Enable/disable
    is_enabled = models.BooleanField(
        default=True, help_text=_("Whether this tool is enabled for the user")
    )

    # Tool configuration
    configuration = models.JSONField(
        default=dict, blank=True, help_text=_("Tool-specific configuration settings")
    )

    # Tool metadata
    description = models.TextField(
        blank=True, null=True, help_text=_("Description of what this tool does")
    )

    category = models.CharField(
        max_length=50,
        default="general",
        choices=[
            ("search", "Search & Retrieval"),
            ("code", "Code Execution"),
            ("data", "Data Processing"),
            ("integration", "External Integration"),
            ("utility", "Utility"),
            ("custom", "Custom"),
        ],
        help_text=_("Tool category"),
    )

    # Usage tracking
    usage_count = models.IntegerField(
        default=0, help_text=_("Number of times this tool has been used")
    )

    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this tool was last used")
    )

    # Rate limiting
    rate_limit = models.IntegerField(
        null=True, blank=True, help_text=_("Maximum uses per hour (null = unlimited)")
    )

    rate_limit_period = models.CharField(
        max_length=20,
        default="hour",
        choices=[
            ("minute", "Per Minute"),
            ("hour", "Per Hour"),
            ("day", "Per Day"),
        ],
        help_text=_("Rate limit period"),
    )

    # Permissions
    requires_approval = models.BooleanField(
        default=False, help_text=_("Whether tool usage requires admin approval")
    )

    is_approved = models.BooleanField(
        default=True, help_text=_("Whether usage is approved by admin")
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_tools",
        help_text=_("Admin who approved this tool"),
    )

    approved_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this tool was approved")
    )

    class Meta:
        verbose_name = _("User Tool")
        verbose_name_plural = _("User Tools")
        ordering = ["tool_display_name"]
        unique_together = ["user", "tool_name"]
        indexes = [
            models.Index(
                fields=["user", "is_enabled"], name="usertool_user_enabled_idx"
            ),
            models.Index(fields=["tool_name"], name="usertool_name_idx"),
            models.Index(fields=["category"], name="usertool_category_idx"),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.tool_display_name}"

    def increment_usage(self):
        """Increment usage count and update last used timestamp."""
        from django.utils import timezone

        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at"])

    def check_rate_limit(self):
        """
        Check if user has exceeded rate limit.

        Returns:
            dict: {'allowed': bool, 'remaining': int, 'reset_at': datetime}
        """
        from django.utils import timezone
        from datetime import timedelta

        if not self.rate_limit:
            return {"allowed": True, "remaining": None, "reset_at": None}

        # Calculate time window
        now = timezone.now()
        if self.rate_limit_period == "minute":
            window_start = now - timedelta(minutes=1)
        elif self.rate_limit_period == "hour":
            window_start = now - timedelta(hours=1)
        else:  # day
            window_start = now - timedelta(days=1)

        # Count recent usage
        from .token_usage import TokenUsage

        recent_usage = TokenUsage.objects.filter(
            user=self.user,
            created_at__gte=window_start,
            metadata__tool_name=self.tool_name,
        ).count()

        remaining = max(0, self.rate_limit - recent_usage)
        allowed = recent_usage < self.rate_limit

        # Calculate reset time
        if self.rate_limit_period == "minute":
            reset_at = now + timedelta(minutes=1)
        elif self.rate_limit_period == "hour":
            reset_at = now + timedelta(hours=1)
        else:
            reset_at = now + timedelta(days=1)

        return {
            "allowed": allowed,
            "remaining": remaining,
            "reset_at": reset_at,
            "current_usage": recent_usage,
            "limit": self.rate_limit,
        }

    @classmethod
    def get_user_tools(cls, user, enabled_only=True):
        """Get all tools for a user."""
        queryset = cls.objects.filter(user=user)

        if enabled_only:
            queryset = queryset.filter(is_enabled=True, is_approved=True)

        return queryset

    @classmethod
    def get_tool_config(cls, user, tool_name):
        """Get configuration for a specific tool."""
        try:
            tool = cls.objects.get(user=user, tool_name=tool_name)
            return tool.configuration
        except cls.DoesNotExist:
            return {}


class AvailableTool(TimestampedModel):
    """
    Catalog of available tools that can be enabled by users.

    This is like a "marketplace" of tools. Admins can add new tools here,
    and users can enable them via UserTool.
    """

    # Tool identification
    tool_name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Internal tool name (matches code implementation)"),
    )

    display_name = models.CharField(max_length=255, help_text=_("Human-readable name"))

    # Tool information
    description = models.TextField(
        help_text=_("Detailed description of tool functionality")
    )

    icon = models.CharField(
        max_length=50, blank=True, null=True, help_text=_("Icon class or emoji for UI")
    )

    category = models.CharField(
        max_length=50,
        default="general",
        choices=[
            ("search", "Search & Retrieval"),
            ("code", "Code Execution"),
            ("data", "Data Processing"),
            ("integration", "External Integration"),
            ("utility", "Utility"),
            ("custom", "Custom"),
        ],
        help_text=_("Tool category"),
    )

    # Availability
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this tool is available for use")
    )

    is_public = models.BooleanField(
        default=True, help_text=_("Whether all users can access this tool")
    )

    requires_admin_approval = models.BooleanField(
        default=False, help_text=_("Whether enabling this tool requires admin approval")
    )

    # Configuration schema
    config_schema = models.JSONField(
        default=dict, blank=True, help_text=_("JSON schema for tool configuration")
    )

    default_config = models.JSONField(
        default=dict, blank=True, help_text=_("Default configuration values")
    )

    # Usage
    total_users = models.IntegerField(
        default=0, help_text=_("Number of users who have enabled this tool")
    )

    class Meta:
        verbose_name = _("Available Tool")
        verbose_name_plural = _("Available Tools")
        ordering = ["category", "display_name"]

    def __str__(self):
        return self.display_name
