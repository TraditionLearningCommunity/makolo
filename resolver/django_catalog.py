from __future__ import annotations

import hashlib
import json

from activities.models import Activity, Occurrence
from geography.models import Place
from organizations.models import Organization
from opportunities.models import Opportunity, OpportunitySource, OpportunityPublicationStatus
from prospector.canonicalization import canonicalize_web_url

from .contracts import CanonicalRef, ResolutionAlternative, ResolutionMethod, ResolutionStrength
from .normalization import normalize_text, normalized_hostname
from .ports import EntityLookup

MAX_LOOKUP_CANDIDATES = 25
MAX_SOURCE_CANDIDATES = 100


def _fingerprint(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _canonical_snapshot(domain, obj):
    if domain == "opportunity":
        sources = list(
            obj.sources.order_by("id").values_list(
                "id", "url", "external_reference", "status", "is_primary", "updated_at"
            )
        )
        return {
            "status": obj.publication_status,
            "current_revision": obj.current_revision_id,
            "updated_at": obj.updated_at,
            "sources": sources,
        }
    if domain == "activity":
        return {
            "title": obj.title,
            "space": obj.space_id,
            "owner_profile": obj.owner_profile_id,
            "status": obj.status,
            "updated_at": obj.updated_at,
        }
    if domain == "occurrence":
        return {
            "activity": obj.activity_id,
            "start_date": obj.start_date,
            "start_time": obj.start_time,
            "end_date": obj.end_date,
            "end_time": obj.end_time,
            "timezone": obj.timezone,
            "status": obj.status,
            "updated_at": obj.updated_at,
        }
    if domain == "organization":
        return {
            "name": obj.name,
            "website": obj.website,
            "city": obj.city,
            "country": obj.country,
            "verification_status": obj.verification_status,
            "updated_at": obj.updated_at,
        }
    if domain == "geography_place":
        return {
            "name": obj.name,
            "locality": obj.locality,
            "country_code": obj.country_code,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "is_active": obj.is_active,
            "updated_at": obj.updated_at,
        }
    return None


def _alternative(domain, obj, *, method, strength, basis):
    return ResolutionAlternative(
        canonical_ref=CanonicalRef(domain, str(obj.pk)),
        method=method,
        strength=strength,
        basis_codes=tuple(basis),
        snapshot_fingerprint=_fingerprint(_canonical_snapshot(domain, obj)),
    )


def _source_locator(material):
    try:
        from observer.django_app.models import Observation

        row = (
            Observation.objects.filter(observation_ref=material.observation_ref)
            .values("final_locator", "requested_locator")
            .first()
        )
        if row:
            return row["final_locator"] or row["requested_locator"] or None
    except Exception:
        return None
    return None


def _text_fact(context, *predicates):
    for item in context.get("facts", ()):
        if getattr(item, "predicate", None) not in predicates:
            continue
        value = getattr(item, "value", None)
        if value is not None and getattr(value, "text", None):
            return value.text.strip()
        if value is not None and getattr(value, "raw_text", None):
            return value.raw_text.strip()
    return None


def _date_fact(context, *predicates):
    for item in context.get("facts", ()):
        if getattr(item, "predicate", None) not in predicates:
            continue
        value = getattr(item, "value", None)
        if value is not None and getattr(value, "date_value", None):
            return value.date_value
    return None


class DjangoRealityCatalog:
    """Read-only bounded adapters from interpreted candidates to canonical domains."""

    _MODELS = {
        "opportunity": Opportunity,
        "activity": Activity,
        "occurrence": Occurrence,
        "organization": Organization,
        "geography_place": Place,
    }

    def lookup_entity(self, material, entity, context):
        families = tuple(context.get("families") or ("reality",))
        alternatives = []
        basis = []
        locator = _source_locator(material)
        source_host = normalized_hostname(locator)

        if "opportunity" in families:
            alternatives.extend(self._opportunities(entity, context, locator, source_host))
        if "occurrence" in families:
            alternatives.extend(self._occurrences(entity, context))
        if "activity" in families:
            alternatives.extend(self._activities(entity))
        if "organization" in families:
            alternatives.extend(self._organizations(entity, locator, source_host))
        if "geography_place" in families:
            alternatives.extend(self._places(entity, context))

        dedup = {}
        for item in alternatives:
            key = (item.canonical_ref.domain, item.canonical_ref.object_ref)
            previous = dedup.get(key)
            rank = {ResolutionStrength.POSSIBLE: 0, ResolutionStrength.STRONG: 1, ResolutionStrength.EXACT: 2}
            if previous is None or rank[item.strength] > rank[previous.strength]:
                dedup[key] = item

        external = _text_fact(context, "external_id", "external_reference", "job_id", "event_id", "course_code")
        if external and source_host:
            provisional_identity = f"external:{source_host}:{normalize_text(external)}"
            basis.append("scoped_external_identifier_available")
        else:
            provisional_identity = f"source:{material.target_key}:{families[0]}:{normalize_text(entity.label)}"
        return EntityLookup(
            families=families,
            alternatives=tuple(dedup.values()),
            provisional_identity_key=provisional_identity,
            basis_codes=tuple(basis),
        )

    def validate_output(self, output):
        """Detect canonical rows changing between candidate generation and finalize."""
        for assertion in output.entity_resolutions:
            if assertion.status.value != "matched" or assertion.canonical_ref is None:
                continue
            selected = next(
                (
                    item
                    for item in assertion.alternatives
                    if item.canonical_ref == assertion.canonical_ref
                ),
                None,
            )
            if selected is None or not selected.snapshot_fingerprint:
                return False
            model = self._MODELS.get(assertion.canonical_ref.domain)
            if model is None:
                return False
            try:
                obj = model.objects.get(pk=assertion.canonical_ref.object_ref)
            except (model.DoesNotExist, ValueError):
                return False
            snapshot = _canonical_snapshot(assertion.canonical_ref.domain, obj)
            if snapshot is None or _fingerprint(snapshot) != selected.snapshot_fingerprint:
                return False
        return True

    def _opportunities(self, entity, context, locator, source_host):
        results = []
        canonical = None
        if locator:
            try:
                canonical = canonicalize_web_url(locator)
            except Exception:
                canonical = None
        if canonical:
            source_candidates = OpportunitySource.objects.select_related("opportunity").exclude(
                opportunity__publication_status=OpportunityPublicationStatus.MERGED
            )
            if source_host:
                source_candidates = source_candidates.filter(url__icontains=source_host)
            for source in source_candidates.order_by("id")[:MAX_SOURCE_CANDIDATES]:
                try:
                    known = canonicalize_web_url(source.url)
                except Exception:
                    continue
                if known == canonical:
                    results.append(
                        _alternative(
                            "opportunity",
                            source.opportunity,
                            method=ResolutionMethod.EXACT,
                            strength=ResolutionStrength.EXACT,
                            basis=("known_opportunity_source_url",),
                        )
                    )
        external = _text_fact(context, "external_id", "external_reference", "job_id", "event_id", "course_code")
        if external and source_host:
            for source in OpportunitySource.objects.select_related("opportunity").filter(
                external_reference__iexact=external,
                url__icontains=source_host,
            ).exclude(opportunity__publication_status=OpportunityPublicationStatus.MERGED).order_by("id")[:MAX_LOOKUP_CANDIDATES]:
                if normalized_hostname(source.url) != source_host:
                    continue
                results.append(
                    _alternative(
                        "opportunity",
                        source.opportunity,
                        method=ResolutionMethod.EXACT,
                        strength=ResolutionStrength.EXACT,
                        basis=("scoped_external_identifier",),
                    )
                )
        title_rows = Opportunity.objects.select_related("current_revision").filter(
            current_revision__title__iexact=entity.label
        ).exclude(publication_status=OpportunityPublicationStatus.MERGED).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        for opportunity in title_rows:
            results.append(
                _alternative(
                    "opportunity",
                    opportunity,
                    method=ResolutionMethod.HEURISTIC,
                    strength=ResolutionStrength.POSSIBLE,
                    basis=("title_only_insufficient",),
                )
            )
        return results

    def _activities(self, entity):
        rows = Activity.objects.filter(title__iexact=entity.label).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        return [
            _alternative(
                "activity",
                row,
                method=ResolutionMethod.HEURISTIC,
                strength=ResolutionStrength.POSSIBLE,
                basis=("title_only_insufficient",),
            )
            for row in rows
        ]

    def _occurrences(self, entity, context):
        date_value = _date_fact(context, "start_date", "mentioned_date")
        if date_value is None:
            return []
        rows = list(
            Occurrence.objects.select_related("activity").filter(
                activity__title__iexact=entity.label,
                start_date=date_value,
            ).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        )
        return [
            _alternative(
                "occurrence",
                row,
                method=ResolutionMethod.DETERMINISTIC,
                strength=ResolutionStrength.STRONG if len(rows) == 1 else ResolutionStrength.POSSIBLE,
                basis=("activity_title_and_occurrence_date",),
            )
            for row in rows
        ]

    def _organizations(self, entity, locator, source_host):
        rows = Organization.objects.filter(name__iexact=entity.label).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        results = []
        for row in rows:
            website_host = normalized_hostname(row.website)
            if row.website and locator:
                try:
                    same_url = canonicalize_web_url(row.website) == canonicalize_web_url(locator)
                except Exception:
                    same_url = False
            else:
                same_url = False
            if same_url:
                strength = ResolutionStrength.STRONG
                method = ResolutionMethod.DETERMINISTIC
                basis = ("exact_name", "exact_known_website_url")
            elif source_host and website_host and source_host == website_host:
                strength = ResolutionStrength.STRONG
                method = ResolutionMethod.DETERMINISTIC
                basis = ("exact_name", "known_website_host")
            else:
                strength = ResolutionStrength.POSSIBLE
                method = ResolutionMethod.HEURISTIC
                basis = ("name_only_insufficient",)
            results.append(
                _alternative(
                    "organization",
                    row,
                    method=method,
                    strength=strength,
                    basis=basis,
                )
            )
        return results

    def _places(self, entity, context):
        rows = Place.objects.filter(name__iexact=entity.label, is_active=True).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        return [
            _alternative(
                "geography_place",
                row,
                method=ResolutionMethod.HEURISTIC,
                strength=ResolutionStrength.POSSIBLE,
                basis=("place_name_only_insufficient",),
            )
            for row in rows
        ]
