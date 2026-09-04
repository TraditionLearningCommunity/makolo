from django.http import Http404
from django.views.generic import TemplateView

from .credential_selectors import public_credential_by_id


class PublicCredentialVerifyView(TemplateView):
    """Public unlisted verification surface using Trust's opaque UUID pattern."""

    template_name = "trust/credential_verify.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = public_credential_by_id(kwargs["public_id"])
        if credential is None:
            raise Http404
        context["credential"] = credential
        return context
