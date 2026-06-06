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
    first_name = models.CharField(max_length=100, verbose_name=_("first name"))
    last_name = models.CharField(max_length=100, verbose_name=_("last name"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("email"))
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("phone"))
    school = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("school"),
        help_text=_("School name"),
    )
    grade = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("grade"),
        help_text=_("Grade/Level (e.g., '10th grade', 'Q1')"),
    )
    subjects = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("subjects"),
        help_text=_("Subjects (comma-separated, e.g., 'Math, German, English')"),
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("notes"),
        help_text=_("Additional notes about the student"),
    )
    booking_code_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("SHA-256 hash of the public booking code (never store plaintext)"),
    )
    is_adult = models.BooleanField(
        default=False,
        verbose_name=_("Erwachsener Schüler"),
        help_text=_("Wenn aktiviert, wird kein Eltern-Portal-Zugang angeboten."),
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


class StudentDocument(models.Model):
    """Unterrichtsmaterial / Dokument – von Tutor oder Schüler/Eltern hochgeladen."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Schüler"),
    )
    file = models.FileField(
        upload_to="student_documents/",
        verbose_name=_("Datei"),
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Bezeichnung"),
        help_text=_("Optionaler Anzeigename"),
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by_portal_user = models.ForeignKey(
        "portal.PortalUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_documents",
    )
    uploaded_by_tutor = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = _("Schülerdokument")
        verbose_name_plural = _("Schülerdokumente")

    def display_name(self):
        return self.name or self.file.name.split("/")[-1]

    def __str__(self):
        return f"{self.student.full_name} – {self.display_name()}"
