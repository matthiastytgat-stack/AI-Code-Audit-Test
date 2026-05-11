"""
Message Feedback Model - User ratings and feedback on AI responses.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class MessageFeedback(TimestampedModel):
    """
    Store user feedback on AI-generated messages.

    This helps with:
    - Quality monitoring
    - Model fine-tuning
    - User satisfaction tracking
    - Issue identification
    """

    # User and session
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_feedback",
        help_text=_("User who provided feedback"),
    )

    chat_session = models.ForeignKey(
        "chatbot.ChatSession",
        on_delete=models.CASCADE,
        related_name="message_feedback",
        help_text=_("Chat session this feedback belongs to"),
    )

    # Message identification from LangGraph checkpoint
    checkpoint_id = models.CharField(
        max_length=255, help_text=_("LangGraph checkpoint ID containing the message")
    )

    message_index = models.IntegerField(
        help_text=_("Index of the message in the checkpoint")
    )

    # Rating
    rating = models.CharField(
        max_length=20,
        choices=[
            ("thumbs_up", "Thumbs Up 👍"),
            ("thumbs_down", "Thumbs Down 👎"),
            ("excellent", "Excellent"),
            ("good", "Good"),
            ("neutral", "Neutral"),
            ("poor", "Poor"),
            ("very_poor", "Very Poor"),
        ],
        help_text=_("User rating for the message"),
    )

    # Feedback categories
    feedback_categories = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            'Categories of feedback (e.g., ["incorrect", "helpful", "creative"])'
        ),
    )

    # Text feedback
    feedback_text = models.TextField(
        blank=True, null=True, help_text=_("Optional detailed feedback from user")
    )

    # Issue tracking
    reported_issue = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("incorrect", "Incorrect Information"),
            ("harmful", "Harmful Content"),
            ("biased", "Biased Response"),
            ("off_topic", "Off Topic"),
            ("incomplete", "Incomplete Answer"),
            ("technical_error", "Technical Error"),
            ("other", "Other"),
        ],
        help_text=_("Type of issue if reporting a problem"),
    )

    # Context preservation
    message_preview = models.TextField(
        blank=True, null=True, help_text=_("Preview of the message (for admin review)")
    )

    model_used = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("AI model that generated the message"),
    )

    # Admin review
    reviewed = models.BooleanField(
        default=False, help_text=_("Whether admin has reviewed this feedback")
    )

    reviewed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this feedback was reviewed")
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_feedback",
        help_text=_("Admin who reviewed this feedback"),
    )

    admin_notes = models.TextField(
        blank=True, null=True, help_text=_("Internal notes from admin review")
    )

    # Action taken
    action_taken = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("none", "No Action"),
            ("noted", "Noted for Training"),
            ("fixed", "Issue Fixed"),
            ("escalated", "Escalated"),
            ("user_notified", "User Notified"),
        ],
        help_text=_("Action taken based on this feedback"),
    )

    class Meta:
        verbose_name = _("Message Feedback")
        verbose_name_plural = _("Message Feedback")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="msgfeedback_user_date_idx"
            ),
            models.Index(
                fields=["chat_session", "-created_at"],
                name="msgfeedback_session_date_idx",
            ),
            models.Index(fields=["rating"], name="msgfeedback_rating_idx"),
            models.Index(fields=["reported_issue"], name="msgfeedback_issue_idx"),
            models.Index(fields=["reviewed"], name="msgfeedback_reviewed_idx"),
        ]
        unique_together = ["checkpoint_id", "message_index", "user"]

    def __str__(self):
        return f"{self.user.email} - {self.rating} - Session {self.chat_session.title}"

    def mark_reviewed(self, reviewer, action_taken="noted", admin_notes=""):
        """Mark feedback as reviewed by admin."""
        from django.utils import timezone

        self.reviewed = True
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.action_taken = action_taken
        if admin_notes:
            self.admin_notes = admin_notes

        self.save(
            update_fields=[
                "reviewed",
                "reviewed_at",
                "reviewed_by",
                "action_taken",
                "admin_notes",
            ]
        )

    @classmethod
    def get_session_satisfaction(cls, chat_session):
        """
        Get satisfaction metrics for a session.

        Returns:
            dict: Satisfaction stats
        """
        feedback = cls.objects.filter(chat_session=chat_session)

        total = feedback.count()
        if total == 0:
            return {"total": 0, "satisfaction_rate": 0.0}

        positive = feedback.filter(
            rating__in=["thumbs_up", "excellent", "good"]
        ).count()
        negative = feedback.filter(
            rating__in=["thumbs_down", "poor", "very_poor"]
        ).count()

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": total - positive - negative,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0.0,
        }

    @classmethod
    def get_user_satisfaction(cls, user):
        """Get overall satisfaction for user's conversations."""
        feedback = cls.objects.filter(user=user)

        total = feedback.count()
        if total == 0:
            return {"total": 0, "satisfaction_rate": 0.0}

        positive = feedback.filter(
            rating__in=["thumbs_up", "excellent", "good"]
        ).count()

        return {
            "total": total,
            "positive": positive,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0.0,
        }
