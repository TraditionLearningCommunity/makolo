def synthetic_server_error(request):
    """Raise a controlled exception for browser validation of Makolo's 500 page.

    This module is wired only when DJANGO_ENV=e2e and is never exposed in
    development or production URL configuration.
    """
    raise RuntimeError("Synthetic Makolo E2E server error")
