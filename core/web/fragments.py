from __future__ import annotations

from django.utils.cache import patch_vary_headers


def is_fragment_request(request, *, target: str | None = None) -> bool:
    """Return whether the request explicitly asks for an HTMX fragment."""
    if request.headers.get("HX-Request", "").lower() != "true":
        return False
    if target is None:
        return True
    return request.headers.get("HX-Target", "") == target


class FragmentTemplateMixin:
    """Select a lightweight shell template for explicit HTMX main swaps."""

    fragment_template_name: str | None = None
    fragment_target = "main-content"

    def get_template_names(self):
        if (
            self.fragment_template_name
            and is_fragment_request(self.request, target=self.fragment_target)
        ):
            return [self.fragment_template_name]
        return super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ("HX-Request", "HX-Target"))
        return response
