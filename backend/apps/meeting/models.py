import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class MeetingRoom(models.Model):
    """Represents a persistent meeting room tied to a lesson."""

    lesson = models.OneToOneField(
        "lessons.Session",
        on_delete=models.CASCADE,
        related_name="meeting_room",
        verbose_name=_("Lesson"),
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name=_("Room Token"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Meeting Room")
        verbose_name_plural = _("Meeting Rooms")

    def __str__(self):
        return f"Meeting {self.token} – {self.lesson}"

    @property
    def group_name(self):
        return f"meeting_{self.token.hex}"
