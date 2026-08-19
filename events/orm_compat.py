"""Scoped ORM path aliases for callers crossing the Event cutover boundary.

Django resolves relation paths centrally. Rewriting only when traversal has
reached the concrete Event, TicketType or Organization model lets legacy
consumers use their former vocabulary without recreating removed columns.
Every resulting SQL join targets the canonical models.
"""

from django.db.models.sql.query import Query

from organizations.models import Organization
from tickets.models import TicketType

from .models import Event


_MODEL_PATHS = {
    Event: {
        "organization": ("activity", "space"),
        "organization_id": ("activity", "space_id"),
        "organizer": ("activity", "created_by"),
        "organizer_id": ("activity", "created_by_id"),
        "title": ("activity", "title"),
        "short_description": ("activity", "short_description"),
        "description": ("activity", "description"),
        "status": ("activity", "status"),
        "visibility": ("activity", "visibility"),
        "start_at": ("activity", "occurrences", "start_at"),
        "end_at": ("activity", "occurrences", "end_at"),
        "timezone": ("activity", "occurrences", "timezone"),
    },
    TicketType: {
        "price": ("offer", "unit_price"),
        "currency": ("offer", "currency"),
        "quantity_total": ("capacity_pool", "total_quantity"),
        "sales_start_at": ("offer", "available_from"),
        "sales_end_at": ("offer", "available_until"),
        "min_per_order": ("offer", "min_quantity"),
        "max_per_order": ("offer", "max_quantity"),
        "is_active": ("capacity_pool", "is_active"),
    },
    Organization: {
        "events": ("activities", "event_vertical"),
    },
}


def _advance(opts, part):
    if opts is None:
        return None
    try:
        field = opts.get_field(part)
    except Exception:
        return None
    related_model = getattr(field, "related_model", None)
    return related_model._meta if related_model is not None else None


def _rewrite_path(names, opts):
    rewritten = []
    current_opts = opts
    for name in names:
        model = getattr(current_opts, "model", None)
        replacement = _MODEL_PATHS.get(model, {}).get(name)
        if replacement:
            for part in replacement:
                rewritten.append(part)
                current_opts = _advance(current_opts, part)
            continue
        rewritten.append(name)
        current_opts = _advance(current_opts, name)
    return rewritten


def install_orm_path_compat():
    if getattr(Query, "_makolo_event_path_compat", False):
        return
    original_names_to_path = Query.names_to_path
    original_add_select_related = Query.add_select_related

    def names_to_path(query, names, opts, *args, **kwargs):
        return original_names_to_path(query, _rewrite_path(names, opts), opts, *args, **kwargs)

    def add_select_related(query, fields):
        opts = query.model._meta
        rewritten = ["__".join(_rewrite_path(field.split("__"), opts)) for field in fields]
        return original_add_select_related(query, rewritten)

    Query.names_to_path = names_to_path
    Query.add_select_related = add_select_related
    Query._makolo_event_path_compat = True
