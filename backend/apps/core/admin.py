from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _("Profile")
    fields = ["is_premium", "premium_since"]


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ["username", "email", "get_premium_status", "is_staff", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active", "date_joined"]

    def get_premium_status(self, obj):
        if hasattr(obj, "userprofile"):
            return _("Premium") if obj.userprofile.is_premium else _("Standard")
        return _("N/A")

    get_premium_status.short_description = _("Premium Status")


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "is_premium", "premium_since", "created_at"]
    search_fields = ["user__username", "user__email"]
    list_filter = ["is_premium", "created_at", "premium_since"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("User"), {"fields": ("user",)}),
        (_("Premium Status"), {"fields": ("is_premium", "premium_since")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
