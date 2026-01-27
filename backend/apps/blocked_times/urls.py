"""
URL-Konfiguration für BlockedTime-App.
"""

from apps.blocked_times import recurring_views, views
from django.urls import path

app_name = "blocked_times"

urlpatterns = [
    path("<int:pk>/", views.BlockedTimeDetailView.as_view(), name="detail"),
    path("create/", views.BlockedTimeCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.BlockedTimeUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.BlockedTimeDeleteView.as_view(), name="delete"),
    path("bulk-delete/", views.BlockedTimeBulkDeleteView.as_view(), name="bulk_delete"),
    # Recurring BlockedTime URLs
    path(
        "recurring/<int:pk>/",
        recurring_views.RecurringBlockedTimeDetailView.as_view(),
        name="recurring_detail",
    ),
    path(
        "recurring/create/",
        recurring_views.RecurringBlockedTimeCreateView.as_view(),
        name="recurring_create",
    ),
    path(
        "recurring/<int:pk>/update/",
        recurring_views.RecurringBlockedTimeUpdateView.as_view(),
        name="recurring_update",
    ),
    path(
        "recurring/<int:pk>/delete/",
        recurring_views.RecurringBlockedTimeDeleteView.as_view(),
        name="recurring_delete",
    ),
    path(
        "recurring/<int:pk>/generate/",
        recurring_views.RecurringBlockedTimeGenerateView.as_view(),
        name="recurring_generate",
    ),
]
