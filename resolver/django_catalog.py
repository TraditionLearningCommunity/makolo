from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

from activities.models import Activity, Occurrence
from geography.models import Place
from organizations.models import Organization
from opportunities.models import Opportunity, OpportunitySource, OpportunityPublicationStatus
from prospector.canonicalization import canonicalize_web_url

from .contracts import CanonicalRef, ResolutionAlternative, ResolutionMethod, ResolutionStrength
from .normalization import normalize_text, normalized_hostname
from .ports import EntityLookup

MAX_LOOKUP_CANDIDATES = 25


def _fingerprint(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _alternative(domain, obj, *, method, strength, basis, snapshot):
    return ResolutionAlternative(
        canonical_ref=CanonicalRef(domain, str(obj.pk)),
        method=method,
        strength=strength,
        basis_codes=tuple(basis),
        snapshot_fingerprint=_fingerprint(snapshot),
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

    def _opportunities(self, entity, context, locator, source_host):
        results = []
        if locator:
            try:
                canonical = canonicalize_web_url(locator)
            except Exception:
                canonical = None
            if canonical:
                for source in OpportunitySource.objects.select_related("opportunity").exclude(
                    opportunity__publication_status=OpportunityPublicationStatus.MERGED
                ).order_by("id")[:1000]:
                    try:
                        known = canonicalize_web_url(source.url)
                    except Exception:
                        continue
                    if known == canonical:
                        opportunity = source.opportunity
                        results.append(
                            _alternative(
                                "opportunity",
                                opportunity,
                                method=ResolutionMethod.EXACT,
                                strength=ResolutionStrength.EXACT,
                                basis=("known_opportunity_source_url",),
                                snapshot={
                                    "status": opportunity.publication_status,
                                    "current_revision": opportunity.current_revision_id,
                                    "source": str(source.pk),
                                    "source_status": source.status,
                                    "updated_at": opportunity.updated_at,
                                },
                            )
                        )
        external = _text_fact(context, "external_id", "external_reference", "job_id", "event_id", "course_code")
        if external and source_host:
            for source in OpportunitySource.objects.select_related("opportunity").filter(
                external_reference__iexact=external
            ).exclude(opportunity__publication_status=OpportunityPublicationStatus.MERGED).order_by("id")[:MAX_LOOKUP_CANDIDATES]:
                if normalized_hostname(source.url) != source_host:
                    continue
                opportunity = source.opportunity
                results.append(
                    _alternative(
                        "opportunity",
                        opportunity,
                        method=ResolutionMethod.EXACT,
                        strength=ResolutionStrength.EXACT,
                        basis=("scoped_external_identifier",),
                        snapshot={
                            "status": opportunity.publication_status,
                            "current_revision": opportunity.current_revision_id,
                            "source": str(source.pk),
                            "external_reference": source.external_reference,
                            "updated_at": opportunity.updated_at,
                        },
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
                    snapshot={
                        "status": opportunity.publication_status,
                        "current_revision": opportunity.current_revision_id,
                        "updated_at": opportunity.updated_at,
                    },
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
                snapshot={
                    "title": row.title,
                    "space": row.space_id,
                    "owner_profile": row.owner_profile_id,
                    "status": row.status,
                    "updated_at": row.updated_at,
                },
            )
            for row in rows
        ]

    def _occurrences(self, entity, context):
        date_value = _date_fact(context, "start_date", "mentioned_date")
        if date_value is None:
            return []
        rows = Occurrence.objects.select_related("activity").filter(
            activity__title__iexact=entity.label,
            start_date=date_value,
        ).order_by("id")[:MAX_LOOKUP_CANDIDATES]
        results = []
        for row in rows:
            strength = ResolutionStrength.STRONG if len(rows) == 1 else ResolutionStrength.POSSIBLE
            results.append(
                _alternative(
                    "occurrence",
                    row,
                    method=ResolutionMethod.DETERMINISTIC,
                    strength=strength,
                    basis=("activity_title_and_occurrence_date",),
                    snapshot={
                        "activity": str(row.activity_id),
                        "start_date": row.start_date,
                        "start_time": row.start_time,
                        "timezone": row.timezone,
                        "status": row.status,
                        "updated_at": row.updated_at,
                    },
                )
            )
        return results

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
                    snapshot={
                        "name": row.name,
                        "website": row.website,
                        "city": row.city,
                        "country": row.country,
                        "verification_status": row.verification_status,
                        "updated_at": row.updated_at,
                    },
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
                snapshot={
                    "name": row.name,
                    "locality": row.locality,
                    "country_code": row.country_code,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "updated_at": row.updated_at,
                },
            )
            for row in rows
        ]
