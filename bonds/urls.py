from django.urls import path
from .views import (
    BondListCreateView,
    BondDetailView,
    BondStatusUpdateView,
)

urlpatterns = [
    path("", BondListCreateView.as_view(), name="bond-list-create"),
    path("<int:pk>/", BondDetailView.as_view(), name="bond-detail"),
    path(
        "<int:pk>/status/",
        BondStatusUpdateView.as_view(),
        name="bond-status-update",
    ),
]