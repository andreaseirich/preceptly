from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import BlockedTime


@admin.register(BlockedTime)
class BlockedTimeAdmin(admin.ModelAdmin):
    list_display = ["title", "start_datetime", "end_datetime", "get_duration", "is_recurring", "created_at"]
    search_fields = ["title", "description"]
    list_filter = ["is_recurring", "start_datetime", "recurring_pattern"]
    date_hierarchy = "start_datetime"
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("Details"), {"fields": ("title", "description")}),
        (_("Time"), {"fields": ("start_datetime", "end_datetime")}),
        (_("Recurrence"), {"fields": ("is_recurring", "recurring_pattern")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_duration(self, obj):
        if obj.start_datetime and obj.end_datetime:
            delta = obj.end_datetime - obj.start_datetime
            hours = delta.total_seconds() / 3600
            return f"{hours:.1f}h"
        return "-"

    get_duration.short_description = _("Duration")
