from collections.abc import Callable

from .types import ReadinessCheck


Contributor = Callable[[object, object | None, object], list[ReadinessCheck]]


class ContributorRegistry:
    def __init__(self):
        self._contributors: list[Contributor] = []

    def register(self, contributor: Contributor):
        if contributor not in self._contributors:
            self._contributors.append(contributor)
        return contributor

    def all(self):
        return tuple(self._contributors)


registry = ContributorRegistry()
