class PrivateNoStoreMixin:
    """Mark authenticated/private API responses as non-cacheable by shared clients."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response
