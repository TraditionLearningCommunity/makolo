from .capabilities import get_web_capabilities


def web_capabilities(request):
    return {"web_capabilities": get_web_capabilities(request.user)}
