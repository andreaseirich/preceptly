from django.urls import path

from apps.portal import views

app_name = "portal"

urlpatterns = [
    path("", views.PortalDispatchView.as_view(), name="home"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", views.PortalLogoutView.as_view(), name="logout"),
    path("student/", views.StudentHomeView.as_view(), name="student_home"),
    path("student/lessons/", views.StudentLessonListView.as_view(), name="student_lessons"),
    path("parent/", views.ParentHomeView.as_view(), name="parent_home"),
    path(
        "parent/<int:student_pk>/",
        views.ParentStudentDetailView.as_view(),
        name="parent_student_detail",
    ),
    path("messages/<int:student_pk>/", views.PortalMessageView.as_view(), name="messages"),
    path("activate/<str:token>/", views.PortalActivateView.as_view(), name="activate"),
    path("password-reset/", views.PortalPasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "student/lessons/<int:pk>/",
        views.StudentLessonDetailView.as_view(),
        name="student_lesson_detail",
    ),
    # Terminbuchung
    path("book/<int:student_pk>/", views.PortalBookingView.as_view(), name="book"),
    path(
        "session/<int:session_pk>/cancel/",
        views.PortalSessionCancelView.as_view(),
        name="session_cancel",
    ),
    path(
        "session/<int:session_pk>/reschedule/",
        views.PortalSessionRescheduleView.as_view(),
        name="session_reschedule",
    ),
    path(
        "availability/<int:student_pk>/",
        views.PortalAvailabilityView.as_view(),
        name="availability",
    ),
    # Serientermine
    path(
        "recurring/<int:student_pk>/",
        views.PortalRecurringManageView.as_view(),
        name="recurring_manage",
    ),
    path(
        "recurring/create/<int:student_pk>/",
        views.PortalRecurringCreateView.as_view(),
        name="recurring_create",
    ),
    path(
        "recurring/<int:recurring_pk>/cancel/",
        views.PortalRecurringCancelView.as_view(),
        name="recurring_cancel",
    ),
    # Dokumente
    path("documents/<int:student_pk>/", views.PortalDocumentsView.as_view(), name="documents"),
    path(
        "documents/<int:student_pk>/<int:doc_pk>/download/",
        views.PortalDocumentDownloadView.as_view(),
        name="document_download",
    ),
]
