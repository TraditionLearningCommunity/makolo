from __future__ import annotations

import logging
from time import perf_counter

from django.conf import settings
from django.db import connection

from .request_context import get_request_context


logger = logging.getLogger("makolo.performance")


def _response_size(response) -> int | None:
    if getattr(response, "streaming", False):
        return None
    try:
        return len(response.content)
    except Exception:
        return None


class PerformanceEnvelopeMiddleware:
    """Lightweight opt-in request envelope; no payloads or PII are logged."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = bool(getattr(settings, "MAKOLO_PERFORMANCE_LOGGING", False))

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        started = perf_counter()
        sql_count = 0
        sql_seconds = 0.0

        def wrapper(execute, sql, params, many, context):
            nonlocal sql_count, sql_seconds
            query_started = perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                sql_count += 1
                sql_seconds += perf_counter() - query_started

        status = 500
        response = None
        try:
            with connection.execute_wrapper(wrapper):
                response = self.get_response(request)
            status = getattr(response, "status_code", 500)
            return response
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            request_context = get_request_context(request)
            match = getattr(request, "resolver_match", None)
            namespace = (match.namespace or "") if match else ""
            url_name = (match.url_name or "") if match else ""
            route = f"{namespace}:{url_name}" if namespace else (url_name or "<unresolved>")
            size = _response_size(response) if response is not None else None
            size_kb = (size / 1024) if size is not None else None

            warn_ms = float(getattr(settings, "MAKOLO_PERFORMANCE_WARN_MS", 0) or 0)
            warn_queries = int(getattr(settings, "MAKOLO_PERFORMANCE_WARN_QUERIES", 0) or 0)
            warn_kb = float(getattr(settings, "MAKOLO_PERFORMANCE_WARN_KB", 0) or 0)
            over_budget = (
                (warn_ms and elapsed_ms > warn_ms)
                or (warn_queries and sql_count > warn_queries)
                or (warn_kb and size_kb is not None and size_kb > warn_kb)
            )
            log = logger.warning if over_budget else logger.info
            log(
                "request_perf route=%s method=%s status=%s duration_ms=%.1f "
                "sql_queries=%s sql_ms=%.1f response_bytes=%s mode=%s request_id=%s",
                route,
                request.method,
                status,
                elapsed_ms,
                sql_count,
                sql_seconds * 1000,
                size if size is not None else "-",
                request_context.surface.mode,
                request_context.request_id,
            )
