from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Iterable, TypeVar


T = TypeVar("T")


@dataclass
class ProjectionBudget:
    """Small response budget shared by composite read models.

    The budget only limits how many already-ordered items a projection may
    expose. It never ranks, recommends or changes owner-domain ordering.
    """

    limit: int
    used: int = 0

    def __post_init__(self):
        self.limit = max(int(self.limit), 0)
        self.used = max(min(int(self.used), self.limit), 0)

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    @property
    def full(self) -> bool:
        return self.remaining == 0

    def take(self, items: Iterable[T]) -> list[T]:
        if self.full:
            return []
        kept = list(islice(items, self.remaining))
        self.used += len(kept)
        return kept
