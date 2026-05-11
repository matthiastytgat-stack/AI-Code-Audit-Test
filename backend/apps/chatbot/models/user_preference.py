"""
User Preference Model - AI chatbot settings and preferences.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class UserPreference(TimestampedModel):
    """
    User-specific AI chatbot preferences and settings.

    Stores default configurations for new chat sessions and
    global user preferences for AI interactions.
    """

    # One preference per user
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_preferences",
        help_text=_("User these preferences belong to"),
    )

    # Default model settings
    default_model = models.CharField(
        max_length=100,
        default="gpt-5-mini",
        choices=[
            ("gpt-5-mini", "GPT-5 Mini (Recommended)"),
            ("gpt-5-nano", "GPT-5 Nano (Smaller/Faster)"),
            ("gpt-4.1-mini", "GPT-4.1 Mini (Faster/Cheaper)"),
            ("gpt-4o-mini", "GPT-4o Mini (Faster/Cheaper)"),
            ("o4-mini", "GPT-o4 Mini (Reasoning)"),
        ],
        help_text=_("Default AI model for new conversations"),
    )

    default_temperature = models.FloatField(
        default=0.7,
        help_text=_("Default temperature (0.0-2.0). Higher = more creative"),
    )

    default_max_tokens = models.IntegerField(
        default=2000, help_text=_("Default max tokens for responses")
    )

    # Summarization preferences
    enable_auto_summarization = models.BooleanField(
        default=True, help_text=_("Enable automatic conversation summarization")
    )

    summarization_trigger_tokens = models.IntegerField(
        default=384, help_text=_("Token count to trigger summarization")
    )

    max_summary_tokens = models.IntegerField(
        default=128, help_text=_("Maximum tokens in summary")
    )

    summarization_style = models.CharField(
        max_length=20,
        default="concise",
        choices=[
            ("concise", "Concise (Brief summaries)"),
            ("detailed", "Detailed (More context)"),
            ("bullet", "Bullet Points"),
        ],
        help_text=_("Style of automatic summaries"),
    )

    # System prompt
    custom_system_prompt = models.TextField(
        blank=True, null=True, help_text=_("Custom system prompt for all conversations")
    )

    use_custom_system_prompt = models.BooleanField(
        default=False, help_text=_("Use custom system prompt instead of default")
    )

    # Response preferences
    response_language = models.CharField(
        max_length=10,
        default="en",
        help_text=_("Preferred response language code (e.g., en, es, fr)"),
    )

    enable_streaming = models.BooleanField(
        default=True, help_text=_("Enable streaming responses (word-by-word)")
    )

    enable_code_execution = models.BooleanField(
        default=False, help_text=_("Allow AI to execute code (advanced users only)")
    )

    # Usage limits
    daily_message_limit = models.IntegerField(
        default=100, help_text=_("Maximum messages per day (0 = unlimited)")
    )

    daily_token_limit = models.IntegerField(
        default=50000, help_text=_("Maximum tokens per day (0 = unlimited)")
    )

    # UI preferences
    theme = models.CharField(
        max_length=20,
        default="auto",
        choices=[
            ("light", "Light Theme"),
            ("dark", "Dark Theme"),
            ("auto", "Auto (System)"),
        ],
        help_text=_("Chat interface theme"),
    )

    show_token_count = models.BooleanField(
        default=False, help_text=_("Show token count in chat interface")
    )

    enable_notifications = models.BooleanField(
        default=True, help_text=_("Enable browser notifications for AI responses")
    )

    # Privacy settings
    save_conversation_history = models.BooleanField(
        default=True, help_text=_("Save conversation history for future reference")
    )

    allow_data_training = models.BooleanField(
        default=False,
        help_text=_("Allow conversations to be used for model improvement"),
    )

    # Advanced settings
    additional_settings = models.JSONField(
        default=dict, blank=True, help_text=_("Additional user-specific settings")
    )

    class Meta:
        verbose_name = _("User Preference")
        verbose_name_plural = _("User Preferences")

    def __str__(self):
        return f"Preferences for {self.user.email}"

    def get_session_config(self):
        """
        Get configuration dict for new chat sessions.

        Returns:
            dict: Configuration for ChatSession and LangGraph
        """
        return {
            "model_name": self.default_model,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "enable_summarization": self.enable_auto_summarization,
            "summarization_threshold": self.summarization_trigger_tokens,
            "max_summary_tokens": self.max_summary_tokens,
            "system_prompt": (
                self.custom_system_prompt if self.use_custom_system_prompt else None
            ),
            "language": self.response_language,
            "streaming": self.enable_streaming,
        }

    @property
    def has_usage_limits(self):
        """Check if user has any usage limits set."""
        return self.daily_message_limit > 0 or self.daily_token_limit > 0
