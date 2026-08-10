import logging
import secrets

from django.shortcuts import render


logger = logging.getLogger(__name__)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    incident_id = f"MKL-{secrets.token_hex(3).upper()}"
    logger.error(
        "Unhandled Makolo server error [%s] path=%s",
        incident_id,
        getattr(request, "path", ""),
    )
    return render(
        request,
        "errors/500.html",
        {"incident_id": incident_id},
        status=500,
    )
