"""
URL-Konfiguration für Billing-App.
"""

from apps.billing import views
from django.urls import path

app_name = "billing"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="invoice_list"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("<int:pk>/delete/", views.InvoiceDeleteView.as_view(), name="invoice_delete"),
    path("create/", views.InvoiceCreateView.as_view(), name="invoice_create"),
    path(
        "<int:pk>/generate-document/",
        views.generate_invoice_document,
        name="invoice_generate_document",
    ),
    path("<int:pk>/document/", views.serve_invoice_document, name="invoice_document"),
    path("<int:pk>/mark-sent/", views.invoice_mark_sent, name="invoice_mark_sent"),
    path("<int:pk>/mark-paid/", views.invoice_mark_paid, name="invoice_mark_paid"),
    path("<int:pk>/undo-paid/", views.invoice_undo_paid, name="invoice_undo_paid"),
    path("<int:pk>/pdf/generate/", views.invoice_pdf_generate, name="invoice_pdf_generate"),
    path("<int:pk>/pdf/", views.invoice_pdf_download, name="invoice_pdf_download"),
]
