"""
URL-Konfiguration für Contract-App.
"""

from django.urls import path

from apps.contracts import views

app_name = "contracts"

urlpatterns = [
    path("", views.ContractListView.as_view(), name="list"),
    path("<int:pk>/", views.ContractDetailView.as_view(), name="detail"),
    path("create/", views.ContractCreateView.as_view(), name="create"),
    path("<int:pk>/update/", views.ContractUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.ContractDeleteView.as_view(), name="delete"),
    path("tier-config/", views.TierConfigListView.as_view(), name="tier_config_list"),
    path("tier-config/create/", views.TierConfigCreateView.as_view(), name="tier_config_create"),
    path(
        "tier-config/create-tutorspace/",
        views.TierConfigCreateTutorSpaceView.as_view(),
        name="tier_config_create_tutorspace",
    ),
    path(
        "tier-config/<int:pk>/update/",
        views.TierConfigUpdateView.as_view(),
        name="tier_config_update",
    ),
    path(
        "tier-config/<int:pk>/delete/",
        views.TierConfigDeleteView.as_view(),
        name="tier_config_delete",
    ),
]
