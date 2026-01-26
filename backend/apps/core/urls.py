"""
URL-Konfiguration für Core-App (Dashboard, Einnahmen, Authentication).
"""

from apps.core import views
from apps.core.views_auth import TutorFlowLoginView, TutorFlowLogoutView
from apps.core.views_health import health_status
from apps.core.views_pwa import manifest_view, service_worker_view
from django.urls import path

app_name = "core"

urlpatterns = [
    path("health/", health_status, name="health"),
    path("login/", TutorFlowLoginView.as_view(), name="login"),
    path("logout/", TutorFlowLogoutView.as_view(), name="logout"),
    path("landing/", views.LandingPageView.as_view(), name="landing"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("income/", views.IncomeOverviewView.as_view(), name="income"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
    # PWA routes
    path("manifest.json", manifest_view, name="manifest"),
    path("sw.js", service_worker_view, name="service_worker"),
]
