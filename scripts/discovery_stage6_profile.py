"""Read-only, opt-in stage 6 profiler for the Discovery server projection.

Usage from the repository root:
    python manage.py shell -c "exec(open('scripts/discovery_stage6_profile.py', encoding='utf-8').read())"

Measures guest/anonymous Discovery exactly like an unauthenticated HTTP request.
This is NOT an HTTP/network benchmark and does not exercise authenticated viewers.
No SQL text, identities, coordinates, payloads or credentials are printed.
No persistent monkeypatches: every instrumented function is restored in finally.
"""
from collections import defaultdict
from contextlib import contextmanager
import json
import os
from statistics import median
from time import perf_counter

from django.contrib.auth.models import AnonymousUser
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.http import QueryDict
from rest_framework.renderers import JSONRenderer

import discovery.api.composition as composition


def _positive_runs():
    try:
        count = int(os.environ.get("MAKOLO_STAGE6_RUNS", "3"))
    except ValueError as exc:
        raise ValueError("MAKOLO_STAGE6_RUNS must be an integer") from exc
    if not 1 <= count <= 10:
        raise ValueError("MAKOLO_STAGE6_RUNS must be between 1 and 10")
    return count


@contextmanager
def _measure_projection():
    original = {}
    measured = defaultdict(lambda: {"ms": 0.0, "calls": 0, "queries": 0, "sql_ms": 0.0})
    stack = []

    def instrument(name, function):
        def wrapped(*args, **kwargs):
            stack.append(name)
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                measured[name]["ms"] += (perf_counter() - started) * 1000
                measured[name]["calls"] += 1
                stack.pop()
        return wrapped

    def sql_counter(execute, sql, params, many, context):
        label = stack[-1] if stack else "other"
        started = perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            measured[label]["queries"] += 1
            measured[label]["sql_ms"] += (perf_counter() - started) * 1000

    names = ("compose_discovery", "project_rows", "spatial_index_from_rows", "spatial_discovery_projection")
    for name in names:
        original[name] = getattr(composition, name)
        setattr(composition, name, instrument(name, original[name]))
    try:
        with connection.execute_wrapper(sql_counter):
            yield measured
    finally:
        for name, function in original.items():
            setattr(composition, name, function)


def _run_once():
    params = QueryDict("page_size=24&include_spatial_index=1")
    started = perf_counter()
    with _measure_projection() as phases:
        data = composition.paginated_projection(params, profile=AnonymousUser())
    projection_ms = (perf_counter() - started) * 1000
    serialization_started = perf_counter()
    wire = JSONRenderer().render(data)
    serialization_ms = (perf_counter() - serialization_started) * 1000
    spatial = data.get("spatial_index") or {}
    # Never print details, user-specific fields or serialized payloads.
    return {
        "projection_ms": projection_ms,
        "serialization_ms": serialization_ms,
        "json_kib": len(wire) / 1024,
        "n1": len(data.get("results") or []),
        "spatial": spatial.get("count", 0),
        "total": data.get("count", 0),
        "phases": {name: dict(result) for name, result in phases.items()},
    }


def main():
    runs = _positive_runs()
    print("Discovery stage 6: anonymous read-only local profile")
    print("Warmup: one sample discarded")
    _run_once()
    samples = []
    for index in range(runs):
        sample = _run_once()
        samples.append(sample)
        print(
            f"Sample {index + 1}/{runs}: "
            f"projection={sample['projection_ms']:.1f} ms, "
            f"json={sample['serialization_ms']:.1f} ms, "
            f"payload={sample['json_kib']:.1f} KiB, "
            f"N1={sample['n1']}, map={sample['spatial']}, total={sample['total']}"
        )
    print("Median timings and SQL measurements (default DB only):")
    for name in ("compose_discovery", "project_rows", "spatial_index_from_rows", "spatial_discovery_projection", "other"):
        values = [sample["phases"].get(name, {}) for sample in samples]
        if not any(values):
            continue
        fmt = lambda key: median(float(value.get(key, 0)) for value in values)
        print(
            f"  {name}: calls={fmt('calls'):.0f} "
            f"wall={fmt('ms'):.1f} ms "
            f"sql_count={fmt('queries'):.0f} "
            f"sql_time={fmt('sql_ms'):.1f} ms"
        )
    print("Note: spatial_discovery_projection includes its nested spatial_index/project_rows timings.")
    print("Note: serialization covers data, not the API envelope, middleware, HTTP or Flutter.")
    print("No domain facts, locations, SQL statements or personal information printed.")


main()
