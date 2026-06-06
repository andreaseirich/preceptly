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
]
