from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError

from .core_models import ConversationContext
from .services import _context_lookup, ensure_context_conversation


@transaction.atomic
def ensure_context_conversation_concurrent(**kwargs):
    """Converge concurrent ensure calls after the losing savepoint is rolled back.

    `ensure_context_conversation` already owns the canonical creation rules. This
    wrapper exists only for real PostgreSQL races: the loser must leave the
    broken savepoint before reading the row committed by the winner.
    """

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
