from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import LessonPlan


@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ["contract", "topic", "subject", "grade_level", "llm_model", "created_at"]
    search_fields = ["contract__first_name", "contract__last_name", "topic", "subject", "content"]
    list_filter = ["subject", "grade_level", "llm_model", "created_at"]
    raw_id_fields = ["contract", "lesson"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("Contract & Lesson"), {"fields": ("contract", "lesson")}),
        (_("Plan Details"), {"fields": ("topic", "subject", "grade_level", "duration_minutes")}),
        (_("Content"), {"fields": ("content",)}),
        (_("AI Metadata"), {"fields": ("llm_model",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
