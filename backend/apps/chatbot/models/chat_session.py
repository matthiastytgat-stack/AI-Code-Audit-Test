"""
Chat Session Model - Maps to LangGraph threads with user-facing metadata.

This model doesn't store messages (LangGraph checkpointer does that).
It stores user-friendly metadata about conversations like titles and settings.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
import uuid


class ChatSession(TimestampedModel):
    """
    Chat session metadata that maps to LangGraph thread_id.

    The actual conversation state (messages, checkpoints) is stored in
    PG_CHECKPOINT_URI by LangGraph's PostgresCheckpointer.

    This model stores user-facing metadata like titles and descriptions.
    """

    # Primary identification
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("UUID that also serves as LangGraph thread_id"),
    )

    # User association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        help_text=_("User who owns this chat session"),
    )

    # User-friendly metadata
    title = models.CharField(
        max_length=255,
        default="New Conversation",
        help_text=_("User-defined or auto-generated conversation title"),
    )

    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional description or summary of the conversation"),
    )

    # Session configuration
    model_name = models.CharField(
        max_length=100,
        default="gpt-5-mini",
        help_text=_("AI model used for this session"),
    )

    temperature = models.FloatField(
        default=0.7, help_text=_("Model temperature (0.0 to 2.0)")
    )

    # Session settings
    enable_summarization = models.BooleanField(
        default=True, help_text=_("Enable automatic conversation summarization")
    )

    summarization_threshold = models.IntegerField(
        default=384, help_text=_("Token count to trigger summarization")
    )

    # Status and visibility
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this session is active")
    )

    is_archived = models.BooleanField(
        default=False, help_text=_("Whether this session is archived")
    )

    is_pinned = models.BooleanField(
        default=False, help_text=_("Whether this session is pinned to top")
    )

    # Additional metadata
    tags = models.JSONField(
        default=list, blank=True, help_text=_("User-defined tags for organization")
    )

    metadata = models.JSONField(
        default=dict, blank=True, help_text=_("Additional session metadata")
    )

    # Analytics
    message_count = models.IntegerField(
        default=0, help_text=_("Total messages in this session (updated via signals)")
    )

    total_tokens_used = models.IntegerField(
        default=0, help_text=_("Total tokens used in this session")
    )

    last_message_at = models.DateTimeField(
        null=True, blank=True, help_text=_("Timestamp of last message in this session")
    )

    class Meta:
        verbose_name = _("Chat Session")
        verbose_name_plural = _("Chat Sessions")
        ordering = ["-is_pinned", "-last_message_at", "-updated_at"]
        indexes = [
            models.Index(
                fields=["user", "-last_message_at"], name="chatsession_user_lastmsg_idx"
            ),
            models.Index(
                fields=["user", "is_active"], name="chatsession_user_active_idx"
            ),
            models.Index(
                fields=["user", "is_archived"], name="chatsession_user_archived_idx"
            ),
            models.Index(
                fields=["is_pinned", "-last_message_at"], name="chatsession_pinned_idx"
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.user.email})"

    @property
    def thread_id(self):
        """Return the UUID as string for use with LangGraph."""
        return str(self.id)

    def update_analytics(self, message_count=None, tokens_used=None, save=True):
        """Update session analytics."""
        from django.utils import timezone

        if message_count is not None:
            self.message_count += message_count

        if tokens_used is not None:
            self.total_tokens_used += tokens_used

        self.last_message_at = timezone.now()

        if save:
            self.save(
                update_fields=["message_count", "total_tokens_used", "last_message_at"]
            )

    def archive(self):
        """Archive this session."""
        self.is_archived = True
        self.is_active = False
        self.save(update_fields=["is_archived", "is_active"])

    def toggle_pin(self):
        """Toggle pin status."""
        self.is_pinned = not self.is_pinned
        self.save(update_fields=["is_pinned"])
