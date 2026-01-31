"""
URL-Konfiguration für Student-App.
"""

from apps.students import views
from django.urls import path

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="list"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="detail"),
    path("create/", views.StudentCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.StudentUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="delete"),
    path(
        "<int:pk>/regenerate-booking-code/",
        views.StudentRegenerateBookingCodeView.as_view(),
        name="regenerate_booking_code",
    ),
]
