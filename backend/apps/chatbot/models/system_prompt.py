"""
System Prompt Template Model - Reusable system prompts for AI.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class SystemPromptTemplate(TimestampedModel):
    """
    Reusable system prompt templates.

    Allows admins and users to create and share system prompts
    for different use cases (coding assistant, writing helper, etc.)
    """

    # Identification
    name = models.CharField(
        max_length=255, unique=True, help_text=_("Unique name for this prompt template")
    )

    slug = models.SlugField(
        max_length=255, unique=True, help_text=_("URL-friendly slug")
    )

    # Content
    content = models.TextField(help_text=_("The system prompt content"))

    description = models.TextField(
        blank=True, null=True, help_text=_("Description of what this prompt does")
    )

    # Categorization
    category = models.CharField(
        max_length=50,
        default="general",
        choices=[
            ("general", "General Purpose"),
            ("coding", "Coding Assistant"),
            ("writing", "Writing Helper"),
            ("research", "Research Assistant"),
            ("education", "Educational"),
            ("business", "Business/Professional"),
            ("creative", "Creative Writing"),
            ("analysis", "Data Analysis"),
            ("custom", "Custom"),
        ],
        help_text=_("Category of this prompt template"),
    )

    tags = models.JSONField(
        default=list, blank=True, help_text=_("Tags for organization and search")
    )

    # Usage settings
    is_default = models.BooleanField(
        default=False, help_text=_("Whether this is the default system prompt")
    )

    is_active = models.BooleanField(
        default=True, help_text=_("Whether this template is active and available")
    )

    is_public = models.BooleanField(
        default=False,
        help_text=_("Whether this template is publicly available to all users"),
    )

    # Variables and customization
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            "List of variables that can be replaced in the prompt (e.g., {user_name}, {topic})"
        ),
    )

    example_variables = models.JSONField(
        default=dict, blank=True, help_text=_("Example values for variables")
    )

    # Recommended settings
    recommended_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Recommended AI model for this prompt"),
    )

    recommended_temperature = models.FloatField(
        null=True, blank=True, help_text=_("Recommended temperature setting")
    )

    # Analytics
    usage_count = models.IntegerField(
        default=0, help_text=_("Number of times this template has been used")
    )

    rating_sum = models.IntegerField(default=0, help_text=_("Sum of all ratings"))

    rating_count = models.IntegerField(default=0, help_text=_("Number of ratings"))

    class Meta:
        verbose_name = _("System Prompt Template")
        verbose_name_plural = _("System Prompt Templates")
        ordering = ["-is_default", "-usage_count", "name"]
        indexes = [
            models.Index(
                fields=["category", "is_active"], name="sysprompt_cat_active_idx"
            ),
            models.Index(fields=["is_default"], name="sysprompt_default_idx"),
            models.Index(fields=["-usage_count"], name="sysprompt_usage_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        """Calculate average rating."""
        if self.rating_count > 0:
            return round(self.rating_sum / self.rating_count, 2)
        return 0.0

    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save(update_fields=["usage_count"])

    def add_rating(self, rating_value):
        """Add a rating (1-5 stars)."""
        if 1 <= rating_value <= 5:
            self.rating_sum += rating_value
            self.rating_count += 1
            self.save(update_fields=["rating_sum", "rating_count"])

    def render(self, variables=None):
        """
        Render the prompt with variables.

        Args:
            variables: dict of variable values

        Returns:
            str: Rendered prompt
        """
        prompt = self.content

        if variables:
            for key, value in variables.items():
                placeholder = "{" + key + "}"
                prompt = prompt.replace(placeholder, str(value))

        return prompt

    @classmethod
    def get_default(cls):
        """Get the default system prompt template."""
        return cls.objects.filter(is_default=True, is_active=True).first()

    @classmethod
    def get_public_templates(cls):
        """Get all public templates."""
        return cls.objects.filter(is_public=True, is_active=True)

    @classmethod
    def get_by_category(cls, category):
        """Get templates by category."""
        return cls.objects.filter(category=category, is_active=True)
