"""
URL configuration for calendar sync (tutor-side CalDAV connection).
"""

from django.urls import path

from apps.calendar_sync import views, views_feed, views_ics

app_name = "calendar_sync"

urlpatterns = [
    path("connect/", views.connect_calendar, name="connect"),
    path("configure/", views.configure_calendars, name="configure"),
    path("disconnect/", views.disconnect_calendar, name="disconnect"),
    path("toggle/", views.toggle_calendar_sync, name="toggle"),
    path("conflicts/", views.conflict_list, name="conflicts"),
    path("conflicts/<int:pk>/resolve/", views.resolve_conflict, name="resolve_conflict"),
    # Kalender per Adresse (Google): nur lesend
    path("address/add/", views_ics.ics_add, name="ics_add"),
    path("address/<int:pk>/sync/", views_ics.ics_sync_now, name="ics_sync_now"),
    path("address/<int:pk>/toggle/", views_ics.ics_toggle, name="ics_toggle"),
    path("address/<int:pk>/remove/", views_ics.ics_remove, name="ics_remove"),
    # Kalender-Abo für Tutoren: der Abruf ist öffentlich (Token), die Verwaltung braucht Login
    path("feed/enable/", views_feed.feed_enable, name="feed_enable"),
    path("feed/renew/", views_feed.feed_renew, name="feed_renew"),
    path("feed/disable/", views_feed.feed_disable, name="feed_disable"),
    path("feed/names/", views_feed.feed_names, name="feed_names"),
    path("feed/<uuid:token>.ics", views_feed.tutor_feed, name="tutor_feed"),
]
