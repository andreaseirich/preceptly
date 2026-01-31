"""
URL configuration for Lesson app.
"""

from apps.lessons import recurring_views, views, views_booking, views_public_booking
from django.urls import path

app_name = "lessons"

urlpatterns = [
    path("", views.LessonListView.as_view(), name="list"),
    path("create/", views.LessonCreateView.as_view(), name="create"),
    path("<int:pk>/", views.LessonDetailView.as_view(), name="detail"),
    path("<int:pk>/conflicts/", views.ConflictDetailView.as_view(), name="conflicts"),
    path("<int:pk>/update/", views.LessonUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.LessonDeleteView.as_view(), name="delete"),
    path("month/<int:year>/<int:month>/", views.LessonMonthView.as_view(), name="month"),
    path("week/", views.WeekView.as_view(), name="week"),
    path("calendar/", views.CalendarView.as_view(), name="calendar"),
    # Recurring Lessons
    path("recurring/", recurring_views.RecurringLessonListView.as_view(), name="recurring_list"),
    path(
        "recurring/<int:pk>/",
        recurring_views.RecurringLessonDetailView.as_view(),
        name="recurring_detail",
    ),
    path(
        "recurring/create/",
        recurring_views.RecurringLessonCreateView.as_view(),
        name="recurring_create",
    ),
    path(
        "recurring/<int:pk>/update/",
        recurring_views.RecurringLessonUpdateView.as_view(),
        name="recurring_update",
    ),
    path(
        "recurring/<int:pk>/delete/",
        recurring_views.RecurringLessonDeleteView.as_view(),
        name="recurring_delete",
    ),
    path(
        "recurring/<int:pk>/generate/",
        recurring_views.generate_lessons_from_recurring,
        name="recurring_generate",
    ),
    path(
        "recurring/bulk-edit/",
        recurring_views.RecurringLessonBulkEditView.as_view(),
        name="recurring_bulk_edit",
    ),
    # Public student booking page
    path(
        "booking/<str:token>/",
        views_booking.StudentBookingView.as_view(),
        name="student_booking",
    ),
    path(
        "booking/<str:token>/api/",
        views_booking.student_booking_api,
        name="student_booking_api",
    ),
    path(
        "booking/<str:token>/week/",
        views_booking.student_booking_week_api,
        name="student_booking_week_api",
    ),
    # Public booking page (optional tutor token for multi-tenancy)
    path(
        "public-booking/",
        views_public_booking.PublicBookingView.as_view(),
        name="public_booking",
    ),
    path(
        "public-booking/<str:tutor_token>/",
        views_public_booking.PublicBookingView.as_view(),
        name="public_booking_with_token",
    ),
    path(
        "public-booking/api/search-student/",
        views_public_booking.search_student_api,
        name="public_booking_search_student",
    ),
    path(
        "public-booking/api/create-student/",
        views_public_booking.create_student_api,
        name="public_booking_create_student",
    ),
    path(
        "public-booking/api/book-lesson/",
        views_public_booking.book_lesson_api,
        name="public_booking_book_lesson",
    ),
]
