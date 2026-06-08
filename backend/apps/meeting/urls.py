from django.urls import path

from apps.meeting import views

app_name = "meeting"

urlpatterns = [
    path("lessons/<int:lesson_pk>/meeting/start/", views.StartMeetingView.as_view(), name="start"),
    path("<uuid:token>/", views.MeetingRoomView.as_view(), name="room"),
    path("<uuid:token>/end/", views.EndMeetingView.as_view(), name="end"),
    path("<uuid:token>/upload/", views.MeetingDocumentUploadView.as_view(), name="upload"),
    path(
        "<uuid:token>/doc/<int:doc_pk>/", views.MeetingDocumentServeView.as_view(), name="doc_serve"
    ),
    path(
        "<uuid:token>/doc/<int:doc_pk>/delete/",
        views.MeetingDocumentDeleteView.as_view(),
        name="doc_delete",
    ),
]
