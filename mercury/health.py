"""Lightweight, unauthenticated health endpoints for mercury.

- ``/healthz`` is a pure liveness probe: it returns 200 without touching the
  database or Ollama, so k8s liveness/readiness checks stay cheap and do not
  depend on the (remote) pgvector host or the GPU box being up.
- ``/version`` reports the build version baked into the image.
"""
from __future__ import annotations

from pathlib import Path

from django.http import JsonResponse

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def _version() -> str:
    try:
        return _VERSION_FILE.read_text().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def healthz(_request):
    return JsonResponse({"status": "ok", "service": "mercury"})


def version(_request):
    return JsonResponse({"service": "mercury", "version": _version()})
