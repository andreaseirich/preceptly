"""
URL configuration for calendar sync (tutor-side CalDAV connection).
"""

from django.urls import path

from apps.calendar_sync import views

app_name = "calendar_sync"

urlpatterns = [
    path("connect/", views.connect_calendar, name="connect"),
    path("disconnect/", views.disconnect_calendar, name="disconnect"),
    path("toggle/", views.toggle_calendar_sync, name="toggle"),
    path("conflicts/", views.conflict_list, name="conflicts"),
    path("conflicts/<int:pk>/resolve/", views.resolve_conflict, name="resolve_conflict"),
]
