from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Student(models.Model):
    """Wird in Migration 0013 entfernt – Daten in Contract migriert."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="students"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    school = models.CharField(max_length=200, blank=True, null=True)
    grade = models.CharField(max_length=50, blank=True, null=True)
    subjects = models.CharField(max_length=500, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    booking_code_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    is_adult = models.BooleanField(default=False)
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
        return f"{self.first_name} {self.last_name}"


class StudentDocument(models.Model):
    """Unterrichtsmaterial / Dokument."""

    student = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Schüler/Vertrag"),
    )
    file = models.FileField(upload_to="student_documents/", verbose_name=_("Datei"))
    name = models.CharField(max_length=200, blank=True, verbose_name=_("Bezeichnung"))
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
