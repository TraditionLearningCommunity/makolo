from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_post_next(request, *, fallback):
    """Return a same-host POST destination or a canonical named fallback."""
    value = (request.POST.get("next") or "").strip()
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return reverse(fallback)
