"""
URL-Konfiguration für BlockedTime-App.
"""

from django.urls import path

from apps.blocked_times import views

app_name = "blocked_times"

urlpatterns = [
    path("<int:pk>/", views.BlockedTimeDetailView.as_view(), name="detail"),
    path("create/", views.BlockedTimeCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.BlockedTimeUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.BlockedTimeDeleteView.as_view(), name="delete"),
]
