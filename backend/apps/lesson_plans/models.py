from apps.lessons.models import Session
from apps.students.models import Student
from django.db import models
from django.utils.translation import gettext_lazy as _


class LessonPlan(models.Model):
    """AI-generated lesson plan with text and metadata."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="lesson_plans",
        help_text=_("Student for whom the plan was created"),
    )
    lesson = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lesson_plans",
        help_text=_("Associated session (optional)"),
    )
    topic = models.CharField(max_length=200, help_text=_("Topic of the lesson plan"))
    subject = models.CharField(max_length=100, help_text=_("Subject (e.g., 'Math', 'German')"))
    content = models.TextField(help_text=_("AI-generated lesson plan (text)"))
    grade_level = models.CharField(
        max_length=50, blank=True, null=True, help_text=_("Grade level (e.g., '10th grade')")
    )
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text=_("Planned duration in minutes")
    )
    llm_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Used LLM model (e.g., 'gpt-4', 'claude-3')"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Lesson Plan")
        verbose_name_plural = _("Lesson Plans")
        indexes = [
            models.Index(fields=["student", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.topic} ({self.subject})"
