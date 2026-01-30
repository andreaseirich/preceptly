from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Student(models.Model):
    """Student with contact information, school/grade and subjects."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="students",
        help_text=_("Tutor who owns this student data"),
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    school = models.CharField(max_length=200, blank=True, null=True, help_text=_("School name"))
    grade = models.CharField(
        max_length=50, blank=True, null=True, help_text=_("Grade/Level (e.g., '10th grade', 'Q1')")
    )
    subjects = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text=_("Subjects (comma-separated, e.g., 'Math, German, English')"),
    )
    notes = models.TextField(
        blank=True, null=True, help_text=_("Additional notes about the student")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = _("Student")
        verbose_name_plural = _("Students")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        """Full name of the student."""
        return f"{self.first_name} {self.last_name}"
