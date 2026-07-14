"""
URL-Konfiguration für Student-App.
"""

from django.urls import path

from apps.students import views

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="list"),
    path("create/", views.StudentCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.StudentUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="delete"),
    path(
        "<int:pk>/regenerate-booking-code/",
        views.StudentRegenerateBookingCodeView.as_view(),
        name="regenerate_booking_code",
    ),
    path(
        "<int:pk>/portal-invite/",
        views.PortalInviteView.as_view(),
        name="portal_invite",
    ),
    path(
        "<int:pk>/progress-note/",
        views.ProgressNoteCreateView.as_view(),
        name="progress_note_create",
    ),
    path(
        "<int:pk>/portal-invite-resend/",
        views.PortalInviteResendView.as_view(),
        name="portal_invite_resend",
    ),
    path(
        "<int:pk>/portal-login-reminder/",
        views.PortalLoginReminderView.as_view(),
        name="portal_login_reminder",
    ),
    path("<int:pk>/documents/", views.StudentDocumentListView.as_view(), name="documents"),
    path(
        "<int:pk>/documents/<int:doc_pk>/delete/",
        views.StudentDocumentDeleteView.as_view(),
        name="document_delete",
    ),
    path(
        "<int:pk>/documents/<int:doc_pk>/download/",
        views.StudentDocumentDownloadView.as_view(),
        name="document_download",
    ),
]
