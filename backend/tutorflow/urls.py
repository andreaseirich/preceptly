"""
URL configuration for tutorflow project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.i18n import set_language

urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("", include("apps.core.urls")),
    path("students/", include("apps.students.urls")),
    path("contracts/", include("apps.contracts.urls")),
    path("lessons/", include("apps.lessons.urls")),
    path("blocked-times/", include("apps.blocked_times.urls")),
    path("billing/", include("apps.billing.urls")),
    path("ai/", include("apps.ai.urls")),
    path("lesson-plans/", include("apps.lesson_plans.urls")),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
