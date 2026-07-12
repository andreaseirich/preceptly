"""
URL-Konfiguration für Contract-App.
"""

from django.urls import path

from apps.contracts import views

app_name = "contracts"

urlpatterns = [
    path("<int:pk>/toggle-active/", views.ContractToggleActiveView.as_view(), name="toggle_active"),
    path("", views.ContractListView.as_view(), name="list"),
    path("<int:pk>/", views.ContractDetailView.as_view(), name="detail"),
    path("create/", views.ContractCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.ContractUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.ContractDeleteView.as_view(), name="delete"),
    path("institutes/", views.InstituteListView.as_view(), name="institute_list"),
    path("institutes/create/", views.InstituteCreateView.as_view(), name="institute_create"),
    path(
        "institutes/<int:pk>/update/",
        views.InstituteUpdateView.as_view(),
        name="institute_update",
    ),
    path(
        "institutes/<int:pk>/delete/",
        views.InstituteDeleteView.as_view(),
        name="institute_delete",
    ),
]
