"""
URL configuration for lesson plans app.
"""

from django.urls import path

from apps.lesson_plans import views

app_name = "lesson_plans"

urlpatterns = [
    path("lessons/<int:lesson_id>/", views.LessonPlanView.as_view(), name="lesson_plan"),
]
