import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


logger = logging.getLogger("app.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        response: Response
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        duration_ms = round((time.monotonic() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_finished request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
