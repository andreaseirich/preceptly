from django.urls import path

from apps.meeting.consumers import MeetingConsumer

websocket_urlpatterns = [
    path("ws/meeting/<uuid:token>/", MeetingConsumer.as_asgi()),
]
