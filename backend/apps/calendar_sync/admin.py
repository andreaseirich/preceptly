from django.contrib import admin

from apps.calendar_sync.models import (
    CalendarConnection,
    ExternalCalendarEventMapping,
    SyncConflict,
    SyncedCalendar,
)


@admin.register(CalendarConnection)
class CalendarConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "sync_enabled", "last_synced_at")
    list_filter = ("provider", "sync_enabled")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("encrypted_password", "created_at", "updated_at")


@admin.register(SyncedCalendar)
class SyncedCalendarAdmin(admin.ModelAdmin):
    list_display = ("connection", "display_name", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("display_name", "external_calendar_url")


@admin.register(ExternalCalendarEventMapping)
class ExternalCalendarEventMappingAdmin(admin.ModelAdmin):
    list_display = ("connection", "content_type", "object_id", "external_uid", "local_synced_at")
    list_filter = ("connection__provider",)
    search_fields = ("external_uid",)


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    list_display = ("connection", "mapping", "created_at", "resolved_at", "resolution")
    list_filter = ("resolution",)
    readonly_fields = ("local_snapshot", "external_snapshot", "created_at")
