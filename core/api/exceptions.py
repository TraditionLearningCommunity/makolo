from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import exceptions as drf_exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def _as_message(value):
    if isinstance(value, Mapping):
        for item in value.values():
            message = _as_message(item)
            if message:
                return message
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            message = _as_message(item)
            if message:
                return message
        return ""
    if value is None:
        return ""
    return str(value)


def _as_list(value):
    if isinstance(value, Mapping):
        return [_as_message(value)] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _validation_fields(data):
    if not isinstance(data, Mapping):
        return {"non_field_errors": _as_list(data)}

    fields = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            fields[str(key)] = [_as_message(value)]
        else:
            fields[str(key)] = _as_list(value)
    return fields


def custom_exception_handler(exc, context):
    """Normalize all expected DRF/Django API errors into one stable envelope.

    Unexpected exceptions are intentionally delegated to Django's normal 500
    handling. Their details and stack traces are never serialized by this
    handler.
    """
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = drf_exceptions.ValidationError(exc.message_dict)
        else:
            exc = drf_exceptions.ValidationError(exc.messages)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    fields = {}
    if isinstance(exc, drf_exceptions.ValidationError):
        code = "validation_error"
        message = "Les données fournies sont invalides."
        fields = _validation_fields(response.data)
    elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
        code = "authentication_required"
        message = _as_message(response.data) or "Authentification requise."
    elif isinstance(exc, drf_exceptions.PermissionDenied):
        code = "permission_denied"
        message = _as_message(response.data) or "Vous n'avez pas la permission d'effectuer cette action."
    elif isinstance(exc, drf_exceptions.NotFound):
        code = "not_found"
        message = _as_message(response.data) or "Ressource introuvable."
    elif isinstance(exc, drf_exceptions.Throttled):
        code = "throttled"
        message = _as_message(response.data) or "Trop de requêtes. Réessayez plus tard."
        if exc.wait is not None:
            fields = {"retry_after_seconds": [str(int(exc.wait))]}
    elif response.status_code == 405:
        code = "method_not_allowed"
        message = _as_message(response.data) or "Méthode HTTP non autorisée."
    else:
        code = "api_error"
        message = _as_message(response.data) or "La requête n'a pas pu être traitée."

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "fields": fields,
        }
    }
    return response
