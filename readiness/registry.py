from collections.abc import Callable

from .types import ReadinessCheck


Contributor = Callable[[object, object | None, object], list[ReadinessCheck]]
DEFAULT_CONTEXT = "journey"


class ContributorRegistry:
    def __init__(self):
        self._contributors: dict[str, list[Contributor]] = {}

    def register(self, contributor=None, *, context=DEFAULT_CONTEXT):
        if contributor is None:
            return lambda wrapped: self.register(wrapped, context=context)
        bucket = self._contributors.setdefault(context, [])
        if contributor not in bucket:
            bucket.append(contributor)
        return contributor

    def all(self, *, context=DEFAULT_CONTEXT):
        return tuple(self._contributors.get(context, ()))


registry = ContributorRegistry()
