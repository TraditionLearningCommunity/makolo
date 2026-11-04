"""Stage 6 Discovery SQL origin diagnosis, anonymous and read-only.

From repository root:
    python manage.py shell -c "exec(open('scripts/discovery_stage6_sql_origins.py', encoding='utf-8').read())"

Prints only repository-relative module/function categories and counts, never SQL,
parameters, object identities, payloads, location or credentials.
Use on a LOCAL development database, not production.
"""
from collections import Counter
from contextlib import contextmanager
from inspect import currentframe
from pathlib import Path
from time import perf_counter

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import QueryDict

from discovery.api.composition import paginated_projection

ROOT = Path.cwd().resolve()
LIMIT = 18


def query_origin():
    frame = currentframe()
    if frame is None:
        return "unknown"
    frame = frame.f_back
    # Find the deepest application call site (closest to SQL) rather than
    # the top-level entrypoint. Exclude Django, site-packages, this file.
    while frame is not None:
        raw_filename = frame.f_code.co_filename
        # manage.py shell -c executes this script as <string>. Resolving
        # that synthetic name against cwd incorrectly classifies our wrapper
        # as an application caller and hides every real SQL origin.
        if raw_filename.startswith("<") or frame.f_code.co_name in {"wrapper", "query_origin"}:
            frame = frame.f_back
            continue
        filename = Path(raw_filename)
        try:
            relative = filename.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            frame = frame.f_back
            continue
        if relative.startswith("scripts/discovery_stage6_sql_origins.py") or relative == "<string>":
            frame = frame.f_back
            continue
        if relative.startswith(("venv/", ".venv/", "env/")):
            frame = frame.f_back
            continue
        if relative.startswith(("django/", "rest_framework/")):
            frame = frame.f_back
            continue
        return f"{relative}:{frame.f_code.co_name}"
    return "external/unknown"


@contextmanager
def observe():
    counts = Counter()
    times = Counter()

    def wrapper(execute, sql, params, many, context):
        # Derive a safe structural origin before executing the SQL. Never
        # retain or print SQL strings or query parameters.
        origin = query_origin()
        started = perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            counts[origin] += 1
            times[origin] += (perf_counter() - started) * 1000

    with connection.execute_wrapper(wrapper):
        yield counts, times


print("Discovery SQL origins: read-only anonymous sample")
print("Caller labels are functions, NOT SQL text or user data")
started = perf_counter()
with observe() as (counts, times):
    result = paginated_projection(
        QueryDict("page_size=24&include_spatial_index=1"),
        profile=AnonymousUser(),
    )
print(
    f"Elapsed: {(perf_counter() - started)*1000:.1f} ms; "
    f"queries: {sum(counts.values())}; N1: {len(result['results'])}; "
    f"map: {result.get('spatial_index', {}).get('count')}; "
    f"total: {result['count']}"
)
print(f"Top {LIMIT} SQL origins by count:")
for origin, count in counts.most_common(LIMIT):
    print(f"  {count:5d} queries; {times[origin]:8.1f} SQL ms; {origin}")
print("Note: queries executed through other DB aliases are not captured.")
print("No SQL statements, query parameters, identifiers or payloads printed.")
