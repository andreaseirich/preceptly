"""
URL-Konfiguration für AI-App.
"""

from django.urls import path

from apps.ai import views

app_name = "ai"

urlpatterns = [
    path(
        "lessons/<int:lesson_id>/generate-plan/",
        views.generate_lesson_plan,
        name="generate_lesson_plan",
    ),
]
