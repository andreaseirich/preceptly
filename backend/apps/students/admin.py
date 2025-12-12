from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "school", "grade", "get_contract_count", "created_at"]
    search_fields = ["first_name", "last_name", "email", "phone", "school"]
    list_filter = ["school", "grade", "created_at"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("Personal Information"), {"fields": ("first_name", "last_name", "email", "phone")}),
        (_("School Information"), {"fields": ("school", "grade", "subjects")}),
        (_("Additional"), {"fields": ("notes",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_contract_count(self, obj):
        return obj.contracts.count()

    get_contract_count.short_description = _("Contracts")
    get_contract_count.admin_order_field = "contracts"
