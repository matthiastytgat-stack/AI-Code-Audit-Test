"""
Token Usage Model - Track AI token consumption and costs.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
from decimal import Decimal


class TokenUsage(TimestampedModel):
    """
    Track token usage and costs for AI interactions.

    This helps with:
    - User billing and quotas
    - Cost analytics
    - Usage patterns
    - Budget management
    """

    # User and session association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="token_usage",
        help_text=_("User who incurred this usage"),
    )

    chat_session = models.ForeignKey(
        "chatbot.ChatSession",
        on_delete=models.CASCADE,
        related_name="token_usage",
        null=True,
        blank=True,
        help_text=_("Chat session this usage belongs to"),
    )

    # Model information
    model_name = models.CharField(
        max_length=100, help_text=_("AI model used (e.g., gpt-4o, gpt-4o-mini)")
    )

    # Token counts
    prompt_tokens = models.IntegerField(
        default=0, help_text=_("Tokens in the prompt/input")
    )

    completion_tokens = models.IntegerField(
        default=0, help_text=_("Tokens in the completion/output")
    )

    total_tokens = models.IntegerField(
        default=0, help_text=_("Total tokens (prompt + completion)")
    )

    # Reasoning tokens (for o3/o4 models)
    reasoning_tokens = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        help_text=_("Reasoning tokens (for models that support it)"),
    )

    # Cost tracking
    prompt_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text=_("Cost for prompt tokens in USD"),
    )

    completion_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text=_("Cost for completion tokens in USD"),
    )

    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text=_("Total cost in USD"),
    )

    # Request metadata
    request_type = models.CharField(
        max_length=50,
        default="chat",
        choices=[
            ("chat", "Chat Completion"),
            ("summarization", "Conversation Summarization"),
            ("embedding", "Text Embedding"),
            ("tool_call", "Tool/Function Call"),
            ("vision", "Vision Analysis"),
        ],
        help_text=_("Type of API request"),
    )

    endpoint = models.CharField(
        max_length=255, blank=True, null=True, help_text=_("API endpoint used")
    )

    # Performance metrics
    response_time_ms = models.IntegerField(
        null=True, blank=True, help_text=_("Response time in milliseconds")
    )

    was_cached = models.BooleanField(
        default=False, help_text=_("Whether response was served from cache")
    )

    # Error tracking
    had_error = models.BooleanField(
        default=False, help_text=_("Whether this request had an error")
    )

    error_message = models.TextField(
        blank=True, null=True, help_text=_("Error message if request failed")
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict, blank=True, help_text=_("Additional usage metadata")
    )

    class Meta:
        verbose_name = _("Token Usage")
        verbose_name_plural = _("Token Usage")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="tokenusage_user_date_idx"
            ),
            models.Index(
                fields=["chat_session", "-created_at"],
                name="tokenusage_session_date_idx",
            ),
            models.Index(fields=["model_name"], name="tokenusage_model_idx"),
            models.Index(fields=["request_type"], name="tokenusage_type_idx"),
            models.Index(
                fields=["user", "model_name"], name="tokenusage_user_model_idx"
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.total_tokens} tokens - ${self.total_cost}"

    def save(self, *args, **kwargs):
        """Calculate total tokens and cost before saving."""
        # Calculate total tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        if self.reasoning_tokens:
            self.total_tokens += self.reasoning_tokens

        # Calculate total cost
        self.total_cost = self.prompt_cost + self.completion_cost

        super().save(*args, **kwargs)

    @classmethod
    def calculate_cost(
        cls, model_name, prompt_tokens, completion_tokens, reasoning_tokens=0
    ):
        """
        Calculate cost based on model pricing.

        Args:
            model_name: Name of the AI model
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            reasoning_tokens: Number of reasoning tokens (for o1/o3 models)

        Returns:
            dict: {'prompt_cost': Decimal, 'completion_cost': Decimal, 'total_cost': Decimal}
        """
        # Pricing per 1M tokens (as of Oct 2025)
        PRICING = {
            "gpt-4o": {
                "prompt": Decimal("2.50"),  # $2.50 per 1M tokens
                "completion": Decimal("10.00"),  # $10.00 per 1M tokens
            },
            "gpt-4o-mini": {
                "prompt": Decimal("0.15"),  # $0.15 per 1M tokens
                "completion": Decimal("0.60"),  # $0.60 per 1M tokens
            },
            "gpt-4-turbo": {
                "prompt": Decimal("10.00"),
                "completion": Decimal("30.00"),
            },
            "gpt-3.5-turbo": {
                "prompt": Decimal("0.50"),
                "completion": Decimal("1.50"),
            },
            "o1-preview": {
                "prompt": Decimal("15.00"),
                "completion": Decimal("60.00"),
            },
            "o1-mini": {
                "prompt": Decimal("3.00"),
                "completion": Decimal("12.00"),
            },
        }

        # Get pricing for model
        model_pricing = PRICING.get(
            model_name, PRICING["gpt-4o-mini"]
        )  # Default to mini

        # Calculate costs (convert to per-token rate)
        prompt_cost = (Decimal(str(prompt_tokens)) * model_pricing["prompt"]) / Decimal(
            "1000000"
        )
        completion_cost = (
            Decimal(str(completion_tokens)) * model_pricing["completion"]
        ) / Decimal("1000000")

        # Reasoning tokens cost same as completion
        if reasoning_tokens:
            completion_cost += (
                Decimal(str(reasoning_tokens)) * model_pricing["completion"]
            ) / Decimal("1000000")

        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "total_cost": prompt_cost + completion_cost,
        }

    @classmethod
    def get_user_usage_today(cls, user):
        """Get user's token usage for today."""
        from django.utils import timezone
        from datetime import timedelta

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        usage = cls.objects.filter(user=user, created_at__gte=today_start).aggregate(
            total_tokens=models.Sum("total_tokens"),
            total_cost=models.Sum("total_cost"),
            message_count=models.Count("id"),
        )

        return {
            "total_tokens": usage["total_tokens"] or 0,
            "total_cost": usage["total_cost"] or Decimal("0.00"),
            "message_count": usage["message_count"] or 0,
        }

    @classmethod
    def check_user_limits(cls, user, additional_tokens=0):
        """
        Check if user has exceeded daily limits.

        Args:
            user: User object
            additional_tokens: Tokens about to be used

        Returns:
            dict: {'allowed': bool, 'reason': str, 'usage': dict}
        """
        try:
            preferences = user.ai_preferences
        except:
            # No preferences set, allow
            return {"allowed": True, "reason": "No limits set", "usage": {}}

        if not preferences.has_usage_limits:
            return {"allowed": True, "reason": "No limits set", "usage": {}}

        usage_today = cls.get_user_usage_today(user)

        # Check message limit
        if preferences.daily_message_limit > 0:
            if usage_today["message_count"] >= preferences.daily_message_limit:
                return {
                    "allowed": False,
                    "reason": f"Daily message limit reached ({preferences.daily_message_limit})",
                    "usage": usage_today,
                }

        # Check token limit
        if preferences.daily_token_limit > 0:
            if (
                usage_today["total_tokens"] + additional_tokens
            ) > preferences.daily_token_limit:
                return {
                    "allowed": False,
                    "reason": f"Daily token limit reached ({preferences.daily_token_limit})",
                    "usage": usage_today,
                }

        return {"allowed": True, "reason": "Within limits", "usage": usage_today}
