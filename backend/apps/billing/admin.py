"""
Admin configuration for Billing app.
"""

from apps.billing.models import Invoice, InvoiceItem
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ["lesson", "description", "date", "duration_minutes", "amount"]
    readonly_fields = ["lesson", "description", "date", "duration_minutes", "amount"]
    raw_id_fields = ["lesson"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "payer_name",
        "get_contract",
        "period_start",
        "period_end",
        "total_amount",
        "get_item_count",
        "status",
        "created_at",
    ]
    list_filter = ["status", "created_at", "period_start", "contract__institute"]
    search_fields = ["payer_name", "payer_address", "contract__student__first_name", "contract__student__last_name"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at", "total_amount"]
    inlines = [InvoiceItemInline]
    raw_id_fields = ["contract"]
    fieldsets = (
        (_("Contract"), {"fields": ("contract",)}),
        (_("Payer Information"), {"fields": ("payer_name", "payer_address")}),
        (_("Period"), {"fields": ("period_start", "period_end")}),
        (_("Amount"), {"fields": ("total_amount",)}),
        (_("Status"), {"fields": ("status",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_contract(self, obj):
        if obj.contract:
            return f"{obj.contract.student.full_name} ({obj.contract.institute or 'Private'})"
        return "-"

    get_contract.short_description = _("Contract")
    get_contract.admin_order_field = "contract__student__last_name"

    def get_item_count(self, obj):
        return obj.items.count()

    get_item_count.short_description = _("Items")


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ["id", "invoice", "get_student_name", "description", "date", "duration_minutes", "amount"]
    list_filter = ["date", "invoice__status", "invoice"]
    search_fields = ["description", "invoice__payer_name", "lesson__contract__student__first_name", "lesson__contract__student__last_name"]
    raw_id_fields = ["invoice", "lesson"]
    readonly_fields = ["invoice", "lesson", "description", "date", "duration_minutes", "amount"]

    def get_student_name(self, obj):
        if obj.lesson and obj.lesson.contract:
            return obj.lesson.contract.student.full_name
        return "-"

    get_student_name.short_description = _("Student")
    get_student_name.admin_order_field = "lesson__contract__student__last_name"
