"""
URL-Konfiguration für Core-App (Dashboard, Einnahmen, Authentication).
"""

from django.urls import path

from apps.core import views
from apps.core.views import (
    ExpenseCreateView,
    ExpenseDeleteView,
    ExpenseListView,
    ExpenseUpdateView,
    TaxYearCsvView,
    TaxYearView,
)
from apps.core.views_auth import RegisterView, TutorFlowLoginView, TutorFlowLogoutView
from apps.core.views_email_test import test_email
from apps.core.views_health import health_status
from apps.core.views_log_test import test_logs
from apps.core.views_pwa import manifest_view, service_worker_view
from apps.core.views_reports import ReportsView
from apps.core.views_stripe import SubscriptionCheckoutView, SubscriptionPortalView

app_name = "core"

urlpatterns = [
    path("health/", health_status, name="health"),
    path("test-logs/", test_logs, name="test_logs"),
    path("test-email/", test_email, name="test_email"),
    path("login/", TutorFlowLoginView.as_view(), name="login"),
    path("logout/", TutorFlowLogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("landing/", views.LandingPageView.as_view(), name="landing"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("income/", views.IncomeOverviewView.as_view(), name="income"),
    path("reports/", ReportsView.as_view(), name="reports"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path(
        "settings/subscription/checkout/",
        SubscriptionCheckoutView.as_view(),
        name="subscription_checkout",
    ),
    path(
        "settings/subscription/portal/",
        SubscriptionPortalView.as_view(),
        name="subscription_portal",
    ),
    # Legal pages
    path("legal/imprint/", views.LegalImprintView.as_view(), name="legal_imprint"),
    path("legal/privacy/", views.LegalPrivacyView.as_view(), name="legal_privacy"),
    path("legal/terms/", views.LegalTermsView.as_view(), name="legal_terms"),
    path("legal/about/", views.LegalAboutView.as_view(), name="legal_about"),
    # PWA routes
    path("manifest.json", manifest_view, name="manifest"),
    path("sw.js", service_worker_view, name="service_worker"),
    path("tax-year/", TaxYearView.as_view(), name="tax_year"),
    path("tax-year/csv/", TaxYearCsvView.as_view(), name="tax_year_csv"),
    path("expenses/", ExpenseListView.as_view(), name="expense_list"),
    path("expenses/new/", ExpenseCreateView.as_view(), name="expense_create"),
    path("expenses/<int:pk>/edit/", ExpenseUpdateView.as_view(), name="expense_update"),
    path("expenses/<int:pk>/delete/", ExpenseDeleteView.as_view(), name="expense_delete"),
]
