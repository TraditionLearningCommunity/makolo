"""Read-only N2 presentation from an admitted Discovery owner projection.

No local alternative inference, no generic ranking and no owner mutations.
"""
from collections import defaultdict

_STATES = ("favorable", "limiting", "unknown")


def _known(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and value.lower() not in {"null", "none", "unknown", "n/a"} else None


def _time(timing, exact, date_key, clock_key):
    if not isinstance(timing, dict):
        return None
    instant = _known(timing.get(exact))
    if instant:
        return instant.replace("T", " ")
    date = _known(timing.get(date_key))
    if not date:
        return None
    return " · ".join(value for value in (
        date, _known(timing.get(clock_key)), _known(timing.get("timezone")),
    ) if value)


def build_n2_presentation(projection):
    """Expose only owner-published values; dimension alignment must be real."""
    assessment = {state: [] for state in _STATES}
    for fact in projection.get("assessment") or []:
        if not isinstance(fact, dict):
            continue
        state = fact.get("state")
        label = _known(fact.get("label"))
        if state in assessment and label and label not in assessment[state]:
            assessment[state].append(label)

    locations = defaultdict(list)
    for fact in projection.get("spatial_facts") or []:
        if not isinstance(fact, dict):
            continue
        occurrence = fact.get("occurrence") or {}
        place = fact.get("place") or {}
        if not isinstance(occurrence, dict) or not isinstance(place, dict):
            continue
        if occurrence.get("kind") != "occurrence":
            continue
        identity = _known(occurrence.get("id"))
        name, locality = _known(place.get("name")), _known(place.get("locality"))
        if not identity:
            continue
        label = (
            f"{name}, {locality}" if name and locality and name.casefold() != locality.casefold()
            else (name or locality)
        )
        if label and label not in locations[identity]:
            locations[identity].append(label)

    variants = []
    seen = set()
    for variant in projection.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        occurrence = variant.get("occurrence") or {}
        if not isinstance(occurrence, dict) or occurrence.get("kind") != "occurrence":
            continue
        identity = _known(occurrence.get("id"))
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        timing = variant.get("timing") or {}
        variants.append({
            "id": identity,
            "start": _time(timing, "start_at", "start_date", "start_time"),
            "end": _time(timing, "end_at", "end_date", "end_time"),
            "places": tuple(locations[identity]),
        })

    comparison = []
    if len(variants) > 1:
        for label, key in (("Début", "start"), ("Fin", "end"), ("Lieu", "places")):
            values = [
                " · ".join(variant[key]) if key == "places" else variant[key]
                for variant in variants
            ]
            if all(values) and len(set(values)) > 1:
                comparison.append({"label": label, "values": tuple(values)})
    relations = []
    for relation in projection.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        label = _known(relation.get("label"))
        if label and label not in relations:
            relations.append(label)

    freshness = projection.get("freshness") or {}
    if not isinstance(freshness, dict):
        freshness = {}
    return {
        "assessment": assessment,
        "variants": tuple(variants),
        "comparison": tuple(comparison),
        "relations": tuple(relations),
        "freshness": _known(freshness.get("label")),
    }
