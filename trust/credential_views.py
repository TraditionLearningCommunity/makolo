from urllib.parse import urlsplit

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from .credential_models import CredentialStatus, CredentialType
from .credential_selectors import credentials_for_profile, public_credential_by_id

def _safe_collection_return(candidate, *, fallback):
    candidate = (candidate or "").strip()
    if not candidate:
        return fallback
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != fallback:
        return fallback
    return candidate



class _PrivateNoStoreTemplateMixin:
    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


class MyCredentialsView(_PrivateNoStoreTemplateMixin, LoginRequiredMixin, TemplateView):
    template_name = "trust/my_credentials.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()[:120]
        status = self.request.GET.get("status", "all")
        credential_type = self.request.GET.get("type", "")
        sort = self.request.GET.get("sort", "recent")
        if status not in {"all", *CredentialStatus.values}:
            status = "all"
        if credential_type not in {"", *CredentialType.values}:
            credential_type = ""
        if sort not in {"recent", "oldest", "title"}:
            sort = "recent"

        credentials = credentials_for_profile(self.request.user)
        if query:
            matching_types = [
                value
                for value, label in CredentialType.choices
                if query.casefold() in label.casefold()
                or query.casefold() in value.casefold()
            ]
            credentials = credentials.filter(
                Q(title__icontains=query)
                | Q(activity__title__icontains=query)
                | Q(issuer_space__name__icontains=query)
                | Q(issuer_profile__first_name__icontains=query)
                | Q(issuer_profile__last_name__icontains=query)
                | Q(issuer_profile__username__icontains=query)
                | Q(credential_type__in=matching_types)
            )
        if status != "all":
            credentials = credentials.filter(status=status)
        if credential_type:
            credentials = credentials.filter(credential_type=credential_type)

        if sort == "oldest":
            credentials = credentials.order_by("issued_at", "id")
        elif sort == "title":
            credentials = credentials.order_by("title", "id")
        else:
            credentials = credentials.order_by("-issued_at", "id")

        page = Paginator(credentials, 24).get_page(
            self.request.GET.get("page")
        )
        context.update(
            {
                "credentials": page.object_list,
                "page": page,
                "query": query,
                "active_status": status,
                "active_type": credential_type,
                "active_sort": sort,
                "type_options": CredentialType.choices,
            }
        )
        return context


class CredentialDetailView(_PrivateNoStoreTemplateMixin, LoginRequiredMixin, TemplateView):
    template_name = "trust/credential_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = credentials_for_profile(self.request.user).filter(
            pk=kwargs["credential_id"]
        ).first()
        if credential is None:
            raise Http404
        context["credential"] = credential
        fallback = reverse("trust:my-credentials")
        context["return_url"] = _safe_collection_return(
            self.request.GET.get("return"),
            fallback=fallback,
        )
        return context


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
