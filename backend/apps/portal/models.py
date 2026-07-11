import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PortalUser(models.Model):
    ROLE_CHOICES = [("parent", _("Parent")), ("student", _("Student"))]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portal_profile"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portal_users"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Portal User")
        verbose_name_plural = _("Portal Users")

    def __str__(self):
        return f"{self.get_role_display()}: {self.user.username}"


class StudentPortalLink(models.Model):
    portal_user = models.OneToOneField(
        PortalUser, on_delete=models.CASCADE, related_name="student_link"
    )
    contract = models.OneToOneField(
        "contracts.Contract", on_delete=models.CASCADE, related_name="portal_link"
    )
    invite_token = models.CharField(max_length=64, unique=True, blank=True)
    invite_token_created_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    reset_token_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Student Portal Link")
        verbose_name_plural = _("Student Portal Links")

    def save(self, *args, **kwargs):
        if not self.invite_token:
            self.invite_token = uuid.uuid4().hex
            self.invite_token_created_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.contract.full_name


class ParentStudentLink(models.Model):
    parent = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="child_links",
        limit_choices_to={"role": "parent"},
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.CASCADE, related_name="parent_links"
    )
    invite_token = models.CharField(max_length=64, unique=True, blank=True)
    invite_token_created_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    reset_token_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("parent", "contract")]
        verbose_name = _("Parent-Student Link")
        verbose_name_plural = _("Parent-Student Links")

    def save(self, *args, **kwargs):
        if not self.invite_token:
            self.invite_token = uuid.uuid4().hex
            self.invite_token_created_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent} → {self.contract.full_name}"


class ProgressNote(models.Model):
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.CASCADE, related_name="progress_notes"
    )
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_notes"
    )
    text = models.TextField(verbose_name=_("Note"))
    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Progress Note")
        verbose_name_plural = _("Progress Notes")

    def __str__(self):
        return f"{self.date} – {self.contract.full_name}"


class PortalMessage(models.Model):
    sender_portal_user = models.ForeignKey(
        PortalUser, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_messages"
    )
    sender_is_tutor = models.BooleanField(default=False)
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.CASCADE, related_name="portal_messages"
    )
    text = models.TextField(verbose_name=_("Message"))
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_tutor = models.BooleanField(default=False, db_index=True)
    read_by_portal = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("Portal Message")
        verbose_name_plural = _("Portal Messages")

    def __str__(self):
        sender = str(self.sender_portal_user) if self.sender_portal_user else "Tutor"
        return f"{sender}: {self.text[:40]}"
