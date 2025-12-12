from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Contract, ContractMonthlyPlan


class ContractMonthlyPlanInline(admin.TabularInline):
    model = ContractMonthlyPlan
    extra = 0
    fields = ["year", "month", "planned_units"]
    readonly_fields = []


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "institute",
        "hourly_rate",
        "unit_duration_minutes",
        "start_date",
        "end_date",
        "is_active",
        "get_lesson_count",
    ]
    search_fields = ["student__first_name", "student__last_name", "institute", "notes"]
    list_filter = ["is_active", "start_date", "institute", "hourly_rate"]
    raw_id_fields = ["student"]
    date_hierarchy = "start_date"
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ContractMonthlyPlanInline]
    fieldsets = (
        (_("Student"), {"fields": ("student",)}),
        (_("Contract Details"), {"fields": ("institute", "hourly_rate", "unit_duration_minutes")}),
        (_("Period"), {"fields": ("start_date", "end_date", "is_active")}),
        (_("Additional"), {"fields": ("notes",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_lesson_count(self, obj):
        return obj.lessons.count()

    get_lesson_count.short_description = _("Lessons")
    get_lesson_count.admin_order_field = "lessons"


@admin.register(ContractMonthlyPlan)
class ContractMonthlyPlanAdmin(admin.ModelAdmin):
    list_display = ["contract", "year", "month", "planned_units", "get_student_name"]
    list_filter = ["year", "month", "contract__is_active"]
    search_fields = ["contract__student__first_name", "contract__student__last_name"]
    raw_id_fields = ["contract"]
    date_hierarchy = "year"

    def get_student_name(self, obj):
        return obj.contract.student.full_name

    get_student_name.short_description = _("Student")
    get_student_name.admin_order_field = "contract__student__last_name"
