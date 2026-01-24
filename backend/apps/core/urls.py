"""
URL-Konfiguration für Core-App (Dashboard, Einnahmen, Authentication).
"""

from apps.core import views
from apps.core.views_auth import TutorFlowLoginView, TutorFlowLogoutView
from apps.core.views_health import health_status
from django.urls import path

app_name = "core"

urlpatterns = [
    path("health/", health_status, name="health"),
    path("login/", TutorFlowLoginView.as_view(), name="login"),
    path("logout/", TutorFlowLogoutView.as_view(), name="logout"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("income/", views.IncomeOverviewView.as_view(), name="income"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
]
