from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import Review, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _("Profile")
    fields = ["subscription_tier", "premium_since"]


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ["username", "email", "get_premium_status", "is_staff", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active", "date_joined"]

    def get_premium_status(self, obj):
        if hasattr(obj, "userprofile"):
            return obj.userprofile.subscription_tier.capitalize()
        return _("N/A")

    get_premium_status.short_description = _("Premium Status")


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "subscription_tier", "premium_since", "created_at"]
    search_fields = ["user__username", "user__email"]
    list_filter = ["subscription_tier", "created_at", "premium_since"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("User"), {"fields": ("user",)}),
        (_("Subscription"), {"fields": ("subscription_tier", "premium_since")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Moderation queue: reviews only appear on the public landing page
    once is_approved is checked here."""

    list_display = ["user", "rating", "is_approved", "created_at"]
    list_editable = ["is_approved"]
    list_filter = ["is_approved", "rating", "created_at"]
    search_fields = ["user__username", "user__email", "comment"]
    readonly_fields = ["created_at", "updated_at"]
