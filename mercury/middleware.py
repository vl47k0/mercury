"""Request middleware for mercury.

RequestIDMiddleware stamps each request with a uuid, exposes it to the JSON
logger via request_id_ctx, echoes it back as X-Request-ID, and logs one
structured line per request.

JWT validation and claim-to-header flattening are NOT done here — the authd
edge performs them and injects X-JWT-* headers (see mercury.authentication).
"""
from __future__ import annotations

import logging
import time
import uuid

from mercury.logging_json import request_id_ctx

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        token = request_id_ctx.set(request.request_id)
        start = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "request_failed",
                extra={
                    "request_id": request.request_id,
                    "method": request.method,
                    "path": request.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = int((time.monotonic() - start) * 1000)
        response["X-Request-ID"] = request.request_id

        logger.info(
            "request",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
