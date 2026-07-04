"""Root URL configuration for mercury."""
from __future__ import annotations

from django.urls import include, path

from mercury.health import healthz, version

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("version", version, name="version"),
    path("api/v1/", include("mail.urls")),
]
