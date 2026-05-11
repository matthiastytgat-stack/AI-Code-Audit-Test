"""
User Document Model - File uploads for RAG (Retrieval Augmented Generation).
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
import os


class UserDocument(TimestampedModel):
    """
    Track user-uploaded documents for RAG.

    The actual embeddings are stored in pgvector (PGVECTOR_CONNECTION_STRING).
    This model stores file metadata and references to vector store.
    """

    # User and session
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text=_("User who uploaded this document"),
    )

    chat_session = models.ForeignKey(
        "chatbot.ChatSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        help_text=_("Chat session this document is associated with"),
    )

    # File information
    file = models.FileField(
        upload_to="user_documents/%Y/%m/%d/", help_text=_("Uploaded document file")
    )

    file_name = models.CharField(max_length=255, help_text=_("Original filename"))

    file_size = models.BigIntegerField(help_text=_("File size in bytes"))

    file_type = models.CharField(max_length=100, help_text=_("MIME type of the file"))

    file_extension = models.CharField(
        max_length=10, help_text=_("File extension (e.g., .pdf, .docx)")
    )

    # Processing status
    processing_status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending Processing"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        help_text=_("Document processing status"),
    )

    processed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When processing completed")
    )

    # Vector store references - REQUIRED for pgvector
    vector_collection_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text=_(
            "PGVector collection name where embeddings are stored (REQUIRED for vector operations)"
        ),
    )

    vector_collection_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Optional metadata for the PGVector collection itself"),
    )

    vector_store_ids = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of pgvector document IDs for this file's chunks"),
    )

    chunk_count = models.IntegerField(
        default=0, help_text=_("Number of chunks/embeddings created")
    )

    # Document metadata
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("User-defined or extracted document title"),
    )

    description = models.TextField(
        blank=True, null=True, help_text=_("User description or summary of document")
    )

    tags = models.JSONField(
        default=list, blank=True, help_text=_("User-defined tags for organization")
    )

    # Extracted content metadata (file-level)
    extracted_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Metadata extracted from document (author, date, pages, etc.)"),
    )

    # Vector metadata - stored with each chunk in pgvector for filtering
    vector_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Searchable metadata for pgvector filtering (e.g., {'user_id': '123', 'category': 'research', 'date': '2025-01'})"
        ),
    )

    page_count = models.IntegerField(
        null=True, blank=True, help_text=_("Number of pages (for PDFs, documents)")
    )

    word_count = models.IntegerField(
        null=True, blank=True, help_text=_("Approximate word count")
    )

    # Visibility and access
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this document is active and searchable")
    )

    is_shared = models.BooleanField(
        default=False, help_text=_("Whether document is shared with other users")
    )

    share_settings = models.JSONField(
        default=dict, blank=True, help_text=_("Document sharing configuration")
    )

    # Error tracking
    processing_error = models.TextField(
        blank=True, null=True, help_text=_("Error message if processing failed")
    )

    retry_count = models.IntegerField(
        default=0, help_text=_("Number of processing retries")
    )

    class Meta:
        verbose_name = _("User Document")
        verbose_name_plural = _("User Documents")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="userdoc_user_date_idx"),
            models.Index(fields=["user", "is_active"], name="userdoc_user_active_idx"),
            models.Index(fields=["processing_status"], name="userdoc_status_idx"),
            models.Index(fields=["file_type"], name="userdoc_type_idx"),
            models.Index(
                fields=["vector_collection_name"], name="userdoc_collection_idx"
            ),
            models.Index(
                fields=["user", "vector_collection_name"],
                name="userdoc_user_collection_idx",
            ),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.user.email})"

    def save(self, *args, **kwargs):
        """Extract file metadata on save."""
        if self.file:
            # Extract filename and extension
            if not self.file_name:
                self.file_name = os.path.basename(self.file.name)

            if not self.file_extension:
                self.file_extension = os.path.splitext(self.file_name)[1].lower()

            # Get file size
            if hasattr(self.file, "size"):
                self.file_size = self.file.size

        super().save(*args, **kwargs)

    def mark_processing_started(self):
        """Mark document as processing."""
        self.processing_status = "processing"
        self.save(update_fields=["processing_status"])

    def mark_processing_completed(
        self,
        collection_name,
        vector_ids,
        chunk_count,
        collection_metadata=None,
        vector_metadata=None,
    ):
        """
        Mark document processing as completed.

        Args:
            collection_name: PGVector collection name (REQUIRED)
            vector_ids: List of document IDs in pgvector
            chunk_count: Number of chunks created
            collection_metadata: Optional metadata for the collection
            vector_metadata: Metadata to be stored with each chunk for filtering
        """
        from django.utils import timezone

        self.processing_status = "completed"
        self.processed_at = timezone.now()
        self.vector_collection_name = collection_name
        self.vector_store_ids = vector_ids
        self.chunk_count = chunk_count

        if collection_metadata:
            self.vector_collection_metadata = collection_metadata

        if vector_metadata:
            self.vector_metadata = vector_metadata

        self.save(
            update_fields=[
                "processing_status",
                "processed_at",
                "vector_collection_name",
                "vector_store_ids",
                "chunk_count",
                "vector_collection_metadata",
                "vector_metadata",
            ]
        )

    def mark_processing_failed(self, error_message):
        """Mark document processing as failed."""
        self.processing_status = "failed"
        self.processing_error = error_message
        self.retry_count += 1

        self.save(
            update_fields=["processing_status", "processing_error", "retry_count"]
        )

    def get_vector_metadata(self):
        """
        Get metadata dict to be stored with vector embeddings.

        Returns:
            dict: Metadata for pgvector filtering
        """
        # Combine vector_metadata with essential fields
        metadata = {
            "user_id": str(self.user.id),
            "document_id": str(self.id),
            "file_name": self.file_name,
            "file_type": self.file_type,
            "upload_date": self.created_at.isoformat(),
        }

        # Add user tags if present
        if self.tags:
            metadata["tags"] = self.tags

        # Add session if present
        if self.chat_session:
            metadata["session_id"] = str(self.chat_session.id)

        # Merge with custom vector_metadata
        if self.vector_metadata:
            metadata.update(self.vector_metadata)

        return metadata

    @property
    def file_size_mb(self):
        """Get file size in MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def is_processable(self):
        """Check if document can be processed for RAG."""
        processable_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
            "application/msword",  # .doc
            "text/plain",
            "text/markdown",
            "text/csv",
        ]
        return self.file_type in processable_types

    @property
    def has_embeddings(self):
        """Check if document has been processed and has embeddings."""
        return bool(
            self.processing_status == "completed"
            and self.vector_collection_name
            and self.vector_store_ids
        )

    @classmethod
    def get_user_storage_usage(cls, user):
        """Get total storage used by user's documents."""
        usage = cls.objects.filter(user=user, is_active=True).aggregate(
            total_size=models.Sum("file_size"),
            total_documents=models.Count("id"),
            total_chunks=models.Sum("chunk_count"),
        )

        return {
            "total_size_bytes": usage["total_size"] or 0,
            "total_size_mb": round((usage["total_size"] or 0) / (1024 * 1024), 2),
            "total_documents": usage["total_documents"] or 0,
            "total_chunks": usage["total_chunks"] or 0,
        }

    @classmethod
    def get_documents_in_collection(cls, collection_name, user=None):
        """
        Get all documents in a specific PGVector collection.

        Args:
            collection_name: Name of the pgvector collection
            user: Optional user filter

        Returns:
            QuerySet: Documents in the collection
        """
        queryset = cls.objects.filter(
            vector_collection_name=collection_name, processing_status="completed"
        )

        if user:
            queryset = queryset.filter(user=user)

        return queryset
