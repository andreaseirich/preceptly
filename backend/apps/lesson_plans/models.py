from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.lessons.models import Session


class LessonPlan(models.Model):
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="lesson_plans",
    )
    lesson = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lesson_plans",
        db_column="lesson_id",
    )
    topic = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    content = models.TextField()
    grade_level = models.CharField(max_length=50, blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    llm_model = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Lesson Plan")
        verbose_name_plural = _("Lesson Plans")
        indexes = [models.Index(fields=["contract", "-created_at"])]

    def __str__(self):
        return f"{self.contract} - {self.topic} ({self.subject})"
