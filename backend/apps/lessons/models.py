from functools import cached_property

from apps.contracts.models import Contract
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# Import RecurringSession for Django recognition


class Session(models.Model):
    """Tutoring session with date, time, status, and travel times."""

    STATUS_CHOICES = [
        ("planned", _("Planned")),
        ("taught", _("Taught")),
        ("cancelled", _("Cancelled")),
        ("paid", _("Paid")),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="sessions",
        help_text=_("Associated contract"),
    )
    date = models.DateField(help_text=_("Session date"))
    start_time = models.TimeField(help_text=_("Start time"))
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text=_("Duration in minutes")
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="planned", help_text=_("Session status")
    )
    travel_time_before_minutes = models.PositiveIntegerField(
        default=0, help_text=_("Travel time before in minutes")
    )
    travel_time_after_minutes = models.PositiveIntegerField(
        default=0, help_text=_("Travel time after in minutes")
    )
    notes = models.TextField(blank=True, null=True, help_text=_("Notes for the session"))
    created_via = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Source: public_booking, contract_booking, or tutor"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lessons_lesson"  # Keep old table name for database compatibility
        ordering = ["-date", "-start_time"]
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")
        indexes = [
            models.Index(fields=["date", "start_time"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"{self.contract.student} - {self.date} {self.start_time} ({self.get_status_display()})"
        )

    @property
    def total_time_minutes(self):
        """Total time including travel times."""
        return (
            self.duration_minutes + self.travel_time_before_minutes + self.travel_time_after_minutes
        )

    @cached_property
    def has_conflicts(self):
        """Checks if this session has conflicts (cached per instance)."""
        from apps.lessons.services import SessionConflictService

        return SessionConflictService.has_conflicts(self)

    def invalidate_conflict_cache(self):
        self.__dict__.pop("has_conflicts", None)

    def get_conflicts(self):
        """Returns all conflicts for this session."""
        from apps.lessons.services import SessionConflictService

        return SessionConflictService.check_conflicts(self)

    def save(self, *args, **kwargs):
        self.invalidate_conflict_cache()
        super().save(*args, **kwargs)


class SessionDocument(models.Model):
    """Document uploaded for a session."""

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text=_("Associated session"),
        db_column="lesson_id",  # Use existing database column name
    )
    file = models.FileField(
        upload_to="session_documents/",
        help_text=_("Document file"),
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text=_("Optional name/description for the document"),
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text=_("Upload timestamp"))

    class Meta:
        db_table = "lessons_lessondocument"  # Keep old table name for database compatibility
        ordering = ["-uploaded_at"]
        verbose_name = _("Session Document")
        verbose_name_plural = _("Session Documents")

    def __str__(self):
        return f"{self.session} - {self.name or self.file.name}"


# Alias for backwards compatibility during migration
Lesson = Session
LessonDocument = SessionDocument
