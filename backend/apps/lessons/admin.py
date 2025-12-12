from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Lesson
from .recurring_models import RecurringLesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = [
        "get_student_name",
        "date",
        "start_time",
        "duration_minutes",
        "status",
        "has_conflicts_display",
        "contract",
    ]
    search_fields = [
        "contract__student__first_name",
        "contract__student__last_name",
        "contract__student__email",
        "notes",
    ]
    list_filter = ["status", "date", "contract__institute", "contract__student"]
    raw_id_fields = ["contract"]
    date_hierarchy = "date"
    readonly_fields = ["created_at", "updated_at", "has_conflicts_display"]
    fieldsets = (
        (_("Contract"), {"fields": ("contract",)}),
        (_("Schedule"), {"fields": ("date", "start_time", "duration_minutes")}),
        (_("Status"), {"fields": ("status",)}),
        (_("Travel Times"), {"fields": ("travel_time_before_minutes", "travel_time_after_minutes")}),
        (_("Conflicts"), {"fields": ("has_conflicts_display",)}),
        (_("Additional"), {"fields": ("notes",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_student_name(self, obj):
        return obj.contract.student.full_name

    get_student_name.short_description = _("Student")
    get_student_name.admin_order_field = "contract__student__last_name"

    def has_conflicts_display(self, obj):
        if obj.has_conflicts:
            conflicts = obj.get_conflicts()
            conflict_types = ", ".join([c["type"] for c in conflicts])
            return _("Yes") + f" ({conflict_types})"
        return _("No")

    has_conflicts_display.short_description = _("Has Conflicts")


@admin.register(RecurringLesson)
class RecurringLessonAdmin(admin.ModelAdmin):
    list_display = [
        "get_student_name",
        "get_weekdays_display",
        "start_time",
        "start_date",
        "end_date",
        "is_active",
    ]
    search_fields = ["contract__student__first_name", "contract__student__last_name", "notes"]
    list_filter = [
        "is_active",
        "start_date",
        "recurrence_type",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    raw_id_fields = ["contract"]
    date_hierarchy = "start_date"
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("Contract"), {"fields": ("contract",)}),
        (_("Schedule"), {"fields": ("start_date", "end_date", "start_time", "duration_minutes")}),
        (_("Recurrence"), {"fields": ("recurrence_type", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Travel Times"), {"fields": ("travel_time_before_minutes", "travel_time_after_minutes")}),
        (_("Additional"), {"fields": ("notes",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_student_name(self, obj):
        return obj.contract.student.full_name

    get_student_name.short_description = _("Student")
    get_student_name.admin_order_field = "contract__student__last_name"

    def get_weekdays_display(self, obj):
        return obj.get_active_weekdays_display()

    get_weekdays_display.short_description = _("Weekdays")
