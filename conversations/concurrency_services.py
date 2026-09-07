from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError

from .core_models import ConversationContext, ConversationContextKind
from .services import _context_lookup, ensure_context_conversation


def _normalized_context_kwargs(kwargs):
    normalized = dict(kwargs)
    if normalized.get("kind") == ConversationContextKind.DIRECT:
        a = normalized.get("direct_profile_a")
        b = normalized.get("direct_profile_b")
        if a is not None and b is not None and str(a.pk) > str(b.pk):
            normalized["direct_profile_a"], normalized["direct_profile_b"] = b, a
    return normalized


@transaction.atomic
def ensure_context_conversation_concurrent(**kwargs):
    """Converge concurrent ensure calls after the losing savepoint is rolled back.

    The wrapper keeps the canonical service as the owner of creation rules, but
    creates a savepoint boundary for PostgreSQL uniqueness races. DIRECT pairs
    are normalized before both lookup and persistence so A/B and B/A resolve to
    the same contextual Conversation.
    """

    kwargs = _normalized_context_kwargs(kwargs)
    kind = kwargs["kind"]
    purpose_key = (kwargs.get("purpose_key") or "coordination").strip().lower()
    targets = {
        field: kwargs.get(field)
        for fields in ConversationContext.TARGET_FIELDS.values()
        for field in fields
    }
    lookup = _context_lookup(kind, purpose_key=purpose_key, targets=targets)
    try:
        with transaction.atomic():
            return ensure_context_conversation(**kwargs)
    except (IntegrityError, TransactionManagementError):
        canonical = ConversationContext.objects.select_related("conversation").filter(**lookup).first()
        if canonical is None:
            raise
        return canonical.conversation
