from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Contract, ContractMonthlyPlan, Institute


class ContractMonthlyPlanInline(admin.TabularInline):
    model = ContractMonthlyPlan
    extra = 0
    fields = ["year", "month", "planned_units"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "institute_fk",
        "hourly_rate",
        "start_date",
        "is_active",
        "get_lesson_count",
    ]
    search_fields = ["first_name", "last_name", "institute_fk__institute_name", "notes", "email"]
    list_filter = ["is_active", "start_date", "institute_fk"]
    date_hierarchy = "start_date"
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ContractMonthlyPlanInline]
    fieldsets = (
        (
            _("Schülerdaten"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "school",
                    "grade",
                    "subjects",
                    "is_adult",
                )
            },
        ),
        (
            _("Contract Details"),
            {"fields": ("user", "institute_fk", "hourly_rate", "unit_duration_minutes")},
        ),
        (_("Period"), {"fields": ("start_date", "end_date", "is_active")}),
        (_("Additional"), {"fields": ("notes",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_lesson_count(self, obj):
        return obj.sessions.count()

    get_lesson_count.short_description = _("Lessons")


@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    list_display = ["institute_name", "user", "unpaid_on_tutor_no_show", "created_at"]
    search_fields = ["institute_name", "user__username"]
    list_filter = ["unpaid_on_tutor_no_show"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ContractMonthlyPlan)
class ContractMonthlyPlanAdmin(admin.ModelAdmin):
    list_display = ["contract", "year", "month", "planned_units", "get_student_name", "created_at"]
    list_filter = ["year", "month", "contract__is_active"]
    search_fields = ["contract__first_name", "contract__last_name"]
    raw_id_fields = ["contract"]
    readonly_fields = ["created_at", "updated_at"]

    def get_student_name(self, obj):
        return obj.contract.full_name

    get_student_name.short_description = _("Student")
    get_student_name.admin_order_field = "contract__last_name"
