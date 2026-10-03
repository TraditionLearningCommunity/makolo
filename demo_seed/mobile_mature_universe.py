from __future__ import annotations

import base64
import hashlib
import io
import wave
import zipfile
from datetime import datetime, time, timedelta
from decimal import Decimal

from PIL import Image
from django.core.files.base import ContentFile

from accounts.models import NotificationPreference, User
from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from capacity.models import CapacityPool
from discovery.models import ActivityBookmark
from events.models import Event, EventCategory, EventVenue, VenueKind, event_cover_path
from funding.models import FundingDetails
from geography.models import Place
from journeys.collaboration_models import JourneyStep, JourneyStepKind, JourneyStepOrigin, JourneyStepStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from obtention.models import ObtentionDetails, ObtentionModeCode
from obtention.services import activate_obtention_journey, create_obtention, create_obtention_journey
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
    OpportunitySave,
    OpportunitySource,
    OpportunitySourceStatus,
    OpportunitySourceType,
)
from organizations.models import Organization
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from services.models import ServiceDetails, ServiceJourneyContext, ServiceKind
from transport.models import (
    TransportDeparture,
    TransportMode,
    TransportRoute,
    TransportRouteStop,
    TransportService,
    Vehicle,
    VehicleType,
)

from .beta import BETA_PERSONAS
from .common import SeedContext, backdate, stable_uuid, upsert
from .mobile_mature_data import REALITY_SPECS


MOBILE_MATURE_PERSONAS = {"primary": "beta.alain@makolo.test"}
MATRIX_REFERENCE_YEAR = 2026
SEED_MARKER = "mobile-mature-universe"
_MP4_DEMO_B64 = "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMvbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAC7gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAlp0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAC7gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAKAAAABaAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAu4AAAAAAABAAAAAAHSbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAAAwABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABfW1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAT1zdGJsAAAAuXN0c2QAAAAAAAAAAQAAAKlhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAKAAWgBIAAAASAAAAAAAAAABFUxhdmM2MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAAL2F2Y0MBQsAK/+EAGGdCwAraCjfkwEQAAAMABAAAAwAIPEiagAEABGjOD8gAAAAQcGFzcAAAAAEAAAABAAAAFGJ0cnQAAAAAAAAHKAAAAAAAAAAYc3R0cwAAAAAAAAABAAAAAwAAQAAAAAAUc3RzcwAAAAAAAAABAAAAAQAAABxzdHNjAAAAAAAAAAEAAAABAAAAAwAAAAEAAAAgc3RzegAAAAAAAAAAAAAAAwAAApsAAAAKAAAACgAAABRzdGNvAAAAAAAAAAEAAANfAAAAYXVkdGEAAABZbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAbWRpcmFwcGwAAAAAAAAAAAAAAAAsaWxzdAAAACSpdG9vAAAAHGRhdGEAAAABAAAAAExhdmY2MS43LjEwMwAAAAhmcmVlAAACt21kYXQAAAJVBgX//1HcRem95tlIt5Ys2CDZI+7veDI2NCAtIGNvcmUgMTY0IHIzMTA4IDMxZTE5ZjkgLSBILjI2NC9NUEPEGNCBBVkMgY29kZWMgLSBDb3B5bGVmdCAyMDAzLTIwMjMgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwgLSBvcHRpb25zOiBjYWJhYz0wIHJlZj0xIGRlYmxvY2s9MDozOjMgYW5hbHlzZT0wOjAgbWU9ZGlhIHN1Ym1lPTAgcHN5PTEgcHN5X3JkPTIuMDA6MC43MCBtaXhlZF9yZWY9MCBtZV9yYW5nZT0xNiBjaHJvbWFfbWU9MSB0cmVsbGlzPTAgOHg4ZGN0PTAgY3FtPTAgZGVhZHpvbmU9MjEsMTEgZmFzdF9wc2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9MCB0aHJlYWRzPTMgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0wIHdlaWdodHA9MCBrZXlpbnQ9MjUwIGtleWludF9taW49MSBzY2VuZWN1dD0wIGludHJhX3JlZnJlc2g9MCByYz1jcmYgbWJ0cmVlPTAgY3JmPTIzLjAgcWNvbXA9MC42MCBxcG1pbj0wIHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MACAAAAAPmWIhDoRigACFvHAAEIiPk5OTk5OTk5OTk5OTrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrwAAAABkGaIBagewAAAAZBmkAXoHs="

PUBLIC_SOURCES = {
    "PUBLIC_FACT:TOWN_EVENT": "https://town-event.com/",
    "DEMO_PUBLIC_ANCHOR:TOWN_EVENT": "https://town-event.com/",
    "PUBLIC_REFERENCE:AIRFAST_ROUTE": "https://airfast-congo.com/",
    "PUBLIC_CATALOGUE_ANCHOR:RDC_SERVICES": "https://servicepublic.gouv.cd/",
    "PUBLIC_REFERENCE:IRCC_STUDY_PERMIT": "https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/study-permit.html",
    "PUBLIC_REFERENCE:IRCC_BIOMETRICS": "https://www.canada.ca/en/immigration-refugees-citizenship/services/biometrics.html",
    "PUBLIC_REFERENCE:IRCC": "https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada.html",
    "PUBLIC_FACT:EDUCANADA_SICS": "https://www.educanada.ca/scholarships-bourses/can/institutions/study-in-canada-sep-etudes-au-canada-pct.aspx?lang=eng",
    "PUBLIC_FACT:EDUCANADA_SEARCH": "https://www.educanada.ca/scholarships-bourses/search-scholarships-rechercher-bourses.aspx?lang=eng",
    "PUBLIC_FACT:AFDB_PEJAB": "https://www.afdb.org/en/projects-and-operations/p-cd-ab0-006",
}

PROVIDERS = {
    "event": ("Lusanga Culture & Rencontres", "mobile-mature-culture", "Rencontres culturelles, ateliers et rendez-vous professionnels à Lubumbashi et dans la région."),
    "transport": ("Horizon Katanga Mobilité", "mobile-mature-mobility", "Solutions de mobilité interurbaine et accompagnement des déplacements professionnels."),
    "service": ("Mwangaza Services", "mobile-mature-services", "Services administratifs, professionnels et pratiques pour accompagner les démarches du quotidien."),
    "funding": ("Kivu Capital & Projets", "mobile-mature-funding", "Accompagnement de projets, budgets, prises en charge et solutions de financement."),
    "obtention": ("Atelier Mosi", "mobile-mature-obtention", "Équipements, locations et solutions d'usage pour les besoins professionnels et personnels."),
}

PUBLIC_SOURCE_LABELS = {
    "PUBLIC_FACT:TOWN_EVENT": "Town-Event — agenda et billetterie RDC",
    "DEMO_PUBLIC_ANCHOR:TOWN_EVENT": "Town-Event — agenda et billetterie RDC",
    "PUBLIC_REFERENCE:AIRFAST_ROUTE": "Air Fast Congo — horaires et informations voyageurs",
    "PUBLIC_CATALOGUE_ANCHOR:RDC_SERVICES": "Catalogue des Services Publics de la RDC",
    "PUBLIC_REFERENCE:IRCC_STUDY_PERMIT": "IRCC — permis d’études au Canada",
    "PUBLIC_REFERENCE:IRCC_BIOMETRICS": "IRCC — biométrie",
    "PUBLIC_REFERENCE:IRCC": "IRCC — étudier au Canada",
    "PUBLIC_FACT:EDUCANADA_SICS": "EduCanada — bourses et programmes",
    "PUBLIC_FACT:EDUCANADA_SEARCH": "EduCanada — moteur de recherche de bourses",
    "PUBLIC_FACT:AFDB_PEJAB": "Banque africaine de développement — PEJAB",
}

VERTICAL_REFERENCE_URLS = {
    "event": ("Agenda public en RDC", "https://town-event.com/"),
    "transport": ("Air Fast Congo — informations voyageurs", "https://airfast-congo.com/"),
    "service": ("Catalogue des Services Publics de la RDC", "https://servicepublic.gouv.cd/"),
    "funding": ("Banque africaine de développement — projets en RDC", "https://www.afdb.org/fr/projects-and-operations/p-cd-ab0-006"),
}

OPPORTUNITY_DIRECTORY_URLS = {
    OpportunityKind.SCHOLARSHIP: ("EduCanada — recherche de bourses", "https://www.educanada.ca/scholarships-bourses/searchAll-rechercheTous.aspx?lang=eng"),
    OpportunityKind.EDUCATION: ("EduCanada — recherche de bourses", "https://www.educanada.ca/scholarships-bourses/searchAll-rechercheTous.aspx?lang=eng"),
    OpportunityKind.PROGRAM: ("Catalogue des Services Publics — éducation et formation", "https://servicepublic.gouv.cd/"),
    OpportunityKind.JOB: ("PNUD — carrières", "https://www.undp.org/fr/careers"),
    OpportunityKind.INTERNSHIP: ("PNUD — carrières", "https://www.undp.org/fr/careers"),
    OpportunityKind.GRANT: ("Catalogue des Services Publics — entrepreneuriat et affaires", "https://servicepublic.gouv.cd/?pv_theme=Entrepreneuriat+et+Affaires"),
    OpportunityKind.COMPETITION: ("Catalogue des Services Publics — entrepreneuriat et affaires", "https://servicepublic.gouv.cd/?pv_theme=Entrepreneuriat+et+Affaires"),
    OpportunityKind.OTHER: ("Banque africaine de développement — projets en RDC", "https://www.afdb.org/fr/projects-and-operations/p-cd-ab0-006"),
}

ISSUERS = (
    "Institut Mwangaza",
    "Réseau Kivu Numérique",
    "Horizon Compétences",
    "Initiative Entrepreneurs du Congo",
    "Programme Atlas",
)

RELATION_LABELS = {
    "experienced": "déjà vécu",
    "completed": "terminé",
    "engaged": "engagé",
    "saved": "conservé",
    "watched": "suivi",
    "discover_only": "à découvrir",
    "planned": "prévu",
    "waiting": "en attente",
    "rejected": "non retenu",
    "abandoned": "abandonné",
    "declined": "refusé",
    "invited": "invitation reçue",
    "draft": "en préparation",
    "space_context": "porté dans un Espace",
}

STATE_LABELS = {
    "completed": "terminé",
    "past": "passé",
    "cancelled": "annulé",
    "ended": "clos",
    "expired": "expiré",
    "fulfilled": "obtenu",
    "returned": "rendu",
    "available": "disponible",
    "open": "ouvert",
    "ongoing": "en cours",
    "waiting": "en attente",
    "upcoming": "à venir",
    "day_of": "aujourd’hui",
    "future": "prévu",
    "planning": "à l’étude",
    "accepted": "accepté",
    "partial": "partiellement financé",
    "ready": "prêt",
    "ready_for_pickup": "prêt à retirer",
    "reserved": "réservé",
    "active_access": "accès actif",
    "negotiation": "en discussion",
}

PLACES = {
    "lubumbashi": ("Lubumbashi", "CD", "-11.664700", "27.479400", "Africa/Lubumbashi"),
    "lubumbashi_airport": ("Aéroport de Lubumbashi", "CD", "-11.591300", "27.530900", "Africa/Lubumbashi"),
    "kolwezi": ("Kolwezi", "CD", "-10.716700", "25.466700", "Africa/Lubumbashi"),
    "kinshasa": ("Kinshasa", "CD", "-4.325000", "15.322200", "Africa/Kinshasa"),
    "likasi": ("Likasi", "CD", "-10.983000", "26.738000", "Africa/Lubumbashi"),
    "kamina": ("Kamina", "CD", "-8.738600", "24.990600", "Africa/Lubumbashi"),
    "kalemie": ("Kalemie", "CD", "-5.947500", "29.194700", "Africa/Lubumbashi"),
    "johannesburg": ("Johannesburg", "ZA", "-26.204100", "28.047300", "Africa/Johannesburg"),
    "montreal": ("Montréal", "CA", "45.501900", "-73.567400", "America/Toronto"),
}

PLACE_ALIASES = {
    "lubumbashi": "lubumbashi",
    "kolwezi": "kolwezi",
    "kinshasa": "kinshasa",
    "likasi": "likasi",
    "kamina": "kamina",
    "kalemie": "kalemie",
    "johannesburg": "johannesburg",
    "montréal": "montreal",
    "montreal": "montreal",
}

TERMINAL_STATES = {"completed", "past", "closed", "cancelled", "ended", "expired", "fulfilled", "returned", "rejected"}


def _principal(ctx: SeedContext) -> User:
    user = upsert(
        User,
        "mobile-mature-primary",
        defaults={
            "email": MOBILE_MATURE_PERSONAS["primary"],
            "username": "beta_alain",
            "first_name": "Alain",
            "last_name": "Kabeya",
            "language": "fr",
            "timezone": "Africa/Lubumbashi",
            "is_active": True,
            "is_verified": True,
            "email_verified": True,
            "onboarding_completed": True,
            "onboarding_step": 5,
            "metadata": {"seed": SEED_MARKER, "persona": "primary", "home_city": "Lubumbashi"},
        },
    )
    user.set_password(ctx.demo_password)
    user.save(update_fields=["password"])
    NotificationPreference.objects.update_or_create(
        user=user,
        defaults={
            "email_notifications": False,
            "sms_notifications": False,
            "push_notifications": False,
            "marketing_notifications": False,
            "security_notifications": True,
            "event_notifications": True,
            "service_notifications": True,
            "opportunity_notifications": True,
        },
    )
    return user


def _providers(owner: User) -> dict[str, Organization]:
    result = {}
    for vertical, (name, slug, description) in PROVIDERS.items():
        space = upsert(
            Organization,
            f"mobile-mature-{vertical}-space",
            defaults={
                "name": name,
                "slug": slug,
                "description": description,
                "contact_email": "",
                "country": "CD",
                "city": "Lubumbashi",
                "public_profile": True,
                "verification_status": "verified",
                "created_by": owner,
            },
        )
        grant_space_role(
            profile=owner,
            space=space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=owner,
            source=SEED_MARKER,
        )
        result[vertical] = space
    return result


def _places(owner: User) -> dict[str, Place]:
    result = {}
    for key, (name, country, lat, lon, tz_name) in PLACES.items():
        result[key] = upsert(
            Place,
            f"mobile-mature-place-{key}",
            defaults={
                "name": name,
                "address_line": "",
                "locality": name,
                "country_code": country,
                "latitude": Decimal(lat),
                "longitude": Decimal(lon),
                "timezone": tz_name,
                "is_active": True,
                "created_by": owner,
            },
        )
    return result


def _place_for(spec: dict, places: dict[str, Place]) -> Place | None:
    raw = (spec.get("geo") or "").lower()
    for token, key in PLACE_ALIASES.items():
        if token in raw:
            return places[key]
    return None


def _scheduled_at(ctx: SeedContext, spec: dict, index: int) -> datetime:
    target_year = ctx.as_of.year + int(spec["year"]) - MATRIX_REFERENCE_YEAR
    tzinfo = ctx.as_of.tzinfo
    if target_year < ctx.as_of.year:
        month = (index * 3) % 12 + 1
        day = (index * 5) % 24 + 2
        return datetime(target_year, month, day, 9 + index % 6, tzinfo=tzinfo)
    if target_year > ctx.as_of.year:
        month = (index * 2) % 12 + 1
        day = (index * 7) % 24 + 2
        return datetime(target_year, month, day, 9 + index % 6, tzinfo=tzinfo)

    state = spec["state"]
    if state == "day_of":
        delta = 0
    elif state in TERMINAL_STATES:
        delta = -(10 + (index * 17) % 180)
    elif state in {"waiting", "ongoing", "negotiation", "partial", "accepted", "active_access"}:
        delta = (index % 9) - 4
    elif state in {"ready", "ready_for_pickup", "reserved"}:
        delta = 1 + index % 4
    else:
        delta = 5 + (index * 7) % 80
    return (ctx.as_of + timedelta(days=delta)).replace(hour=9 + index % 7, minute=0, second=0, microsecond=0)


def _activity_status(spec: dict) -> str:
    if spec["state"] == "cancelled":
        return ActivityStatus.CANCELLED
    if int(spec["year"]) < MATRIX_REFERENCE_YEAR or spec["state"] in TERMINAL_STATES:
        return ActivityStatus.COMPLETED
    return ActivityStatus.PUBLISHED


def _occurrence_status(spec: dict) -> str:
    if spec["state"] == "cancelled":
        return OccurrenceStatus.CANCELLED
    if int(spec["year"]) < MATRIX_REFERENCE_YEAR or spec["state"] in TERMINAL_STATES:
        return OccurrenceStatus.COMPLETED
    return OccurrenceStatus.SCHEDULED


def _activity_copy(spec: dict, vertical: str) -> tuple[str, str]:
    place = spec.get("geo") or "lieu à confirmer"
    relation = RELATION_LABELS.get(spec.get("relation"), spec.get("relation", "à suivre"))
    state = STATE_LABELS.get(spec.get("state"), spec.get("state", "à suivre"))
    intros = {
        "event": "Un rendez-vous culturel, professionnel ou communautaire",
        "transport": "Un déplacement inscrit dans les habitudes de mobilité d’Alain",
        "service": "Un service utile à une démarche personnelle ou professionnelle",
        "funding": "Une possibilité de financement ou de prise en charge",
    }
    intro = intros.get(vertical, "Une possibilité utile")
    short = f"{intro}, à {place}. Situation actuelle : {state}."
    description = (
        f"{spec['title']} fait partie du parcours d’Alain Kabeya. "
        f"Cette réalité est localisée ou rattachée à {place} et apparaît comme {relation}. "
        f"Les dates, accès, ressources et prochaines étapes associés sont disponibles dans Makolo."
    )
    return short[:320], description


def _activity(spec: dict, *, vertical: str, space: Organization, actor: User) -> Activity:
    short_description, description = _activity_copy(spec, vertical)
    return upsert(
        Activity,
        f"mobile-mature-{spec['id'].lower()}",
        defaults={
            "space": space,
            "created_by": actor,
            "title": spec["title"],
            "slug": f"mobile-mature-{spec['id'].lower()}",
            "short_description": short_description,
            "description": description,
            "status": _activity_status(spec),
            "visibility": ActivityVisibility.PUBLIC,
        },
    )


def _occurrence(ctx: SeedContext, spec: dict, *, activity: Activity, place: Place | None, index: int) -> Occurrence:
    start = _scheduled_at(ctx, spec, index)
    occurrence = upsert(
        Occurrence,
        f"mobile-mature-occ-{spec['id'].lower()}",
        defaults={
            "activity": activity,
            "label": spec["title"][:180],
            "start_at": start,
            "end_at": start + timedelta(hours=2 + index % 4),
            "timezone": place.timezone if place else "Africa/Lubumbashi",
            "status": _occurrence_status(spec),
        },
    )
    if place:
        OccurrencePlace.objects.update_or_create(
            occurrence=occurrence,
            role=OccurrencePlaceRole.PRIMARY,
            defaults={"place": place, "position": 0},
        )
    return occurrence


def _png_bytes(key: str, variant: int = 0) -> bytes:
    digest = hashlib.sha256(f"{key}:{variant}".encode()).digest()
    image = Image.new("RGB", (960, 540), (48 + digest[0] % 160, 48 + digest[1] % 160, 48 + digest[2] % 160))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(spec: dict) -> bytes:
    lines = [
        spec["title"],
        f"Lieu : {spec.get('geo') or 'à confirmer'}",
        f"Année : {spec['year']}",
        f"Situation : {STATE_LABELS.get(spec.get('state'), spec.get('state', 'à suivre'))}",
        "Repère : vérifier dans Makolo les dates, ressources et conditions avant l’action.",
    ]
    encoded = [_pdf_escape(line)[:150] for line in lines]
    stream_text = "BT /F1 15 Tf 72 720 Td "
    for position, line in enumerate(encoded):
        if position:
            stream_text += "0 -28 Td /F1 11 Tf "
        stream_text += f"({line}) Tj "
    stream_text += "ET"
    stream = stream_text.encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(objects)+1}\n".encode() + b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(body)


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(8000)
        audio.writeframes(bytes([128]) * 4000)
    return buffer.getvalue()


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _zip_doc(kind: str, spec: dict) -> bytes:
    safe = _xml_escape(spec["title"])
    geo = _xml_escape(spec.get("geo") or "À confirmer")
    state = _xml_escape(STATE_LABELS.get(spec.get("state"), spec.get("state", "À suivre")))
    year = _xml_escape(str(spec["year"]))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if kind == "xlsx":
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            zf.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Suivi" sheetId="1" r:id="rId1"/></sheets></workbook>')
            zf.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            zf.writestr("xl/worksheets/sheet1.xml", f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Activité</t></is></c><c r="B1" t="inlineStr"><is><t>{safe}</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Lieu</t></is></c><c r="B2" t="inlineStr"><is><t>{geo}</t></is></c></row><row r="3"><c r="A3" t="inlineStr"><is><t>Année</t></is></c><c r="B3" t="inlineStr"><is><t>{year}</t></is></c></row><row r="4"><c r="A4" t="inlineStr"><is><t>Situation</t></is></c><c r="B4" t="inlineStr"><is><t>{state}</t></is></c></row></sheetData></worksheet>')
        else:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            zf.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{safe}</w:t></w:r></w:p><w:p><w:r><w:t>Lieu : {geo}</w:t></w:r></w:p><w:p><w:r><w:t>Année : {year} — situation : {state}</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


def _file_resource(ctx: SeedContext, *, activity: Activity, key: str, title: str, filename: str, mime: str, data: bytes) -> ActivityResource:
    pk = stable_uuid(f"mobile-mature-resource:{activity.pk}:{key}")
    content_hash = hashlib.sha256(data).hexdigest()
    existing = ActivityResource.objects.filter(pk=pk).first()
    if existing:
        existing.title = title
        existing.description = f"Document associé à {activity.title}."
        existing.mime_type = mime
        existing.size = len(data)
        if existing.content_hash != content_hash or not existing.file:
            existing.file.save(filename, ContentFile(data), save=False)
        existing.content_hash = content_hash
        existing.visibility = ResourceVisibility.PUBLIC
        existing.save(
            update_fields=[
                "title",
                "description",
                "mime_type",
                "size",
                "file",
                "content_hash",
                "visibility",
                "updated_at",
            ]
        )
        return existing
    resource = ActivityResource(
        pk=pk,
        activity=activity,
        key=key,
        title=title,
        description=f"Document associé à {activity.title}.",
        kind=ResourceKind.FILE,
        mime_type=mime,
        size=len(data),
        content_hash=content_hash,
        visibility=ResourceVisibility.PUBLIC,
        status=ResourceStatus.PUBLISHED,
        version=1,
        created_by=activity.created_by,
        published_at=ctx.as_of,
    )
    resource.file.save(filename, ContentFile(data), save=False)
    resource.save()
    return resource


def _seed_resources(ctx: SeedContext, activity: Activity, spec: dict, index: int) -> None:
    upsert(
        ActivityResource,
        f"mobile-mature-context-{spec['id']}",
        defaults={
            "activity": activity,
            "key": "practical-info",
            "title": "Informations pratiques",
            "description": f"Repères utiles pour {spec['title']}.",
            "kind": ResourceKind.TEXT,
            "text_content": (
                f"{spec['title']} — {spec.get('geo') or 'lieu à confirmer'}. "
                f"Année {spec['year']}. Situation : "
                f"{STATE_LABELS.get(spec.get('state'), spec.get('state', 'à suivre'))}."
            ),
            "visibility": ResourceVisibility.PUBLIC,
            "status": ResourceStatus.PUBLISHED,
            "version": 1,
            "created_by": activity.created_by,
            "published_at": ctx.as_of,
        },
    )
    source = PUBLIC_SOURCES.get(spec["provenance"])
    source_label = PUBLIC_SOURCE_LABELS.get(spec["provenance"], "Référence publique")
    if not source:
        prefix = spec["id"].split("-", 1)[0]
        vertical = {
            "EVT": "event",
            "TRN": "transport",
            "SRV": "service",
            "FND": "funding",
        }.get(prefix)
        if vertical in VERTICAL_REFERENCE_URLS:
            source_label, source = VERTICAL_REFERENCE_URLS[vertical]
    if source:
        upsert(
            ActivityResource,
            f"mobile-mature-source-{spec['id']}",
            defaults={
                "activity": activity,
                "key": "public-source",
                "title": source_label,
                "description": "Ressource publique consultable en ligne pour approfondir ce type de démarche.",
                "kind": ResourceKind.URL,
                "external_url": source,
                "visibility": ResourceVisibility.PUBLIC,
                "status": ResourceStatus.PUBLISHED,
                "version": 1,
                "created_by": activity.created_by,
                "published_at": ctx.as_of,
            },
        )

    media = spec["media"].lower()
    if "magazine_link" in media:
        upsert(
            ActivityResource,
            f"mobile-mature-magazine-{spec['id']}",
            defaults={
                "activity": activity,
                "key": "inflight-magazine",
                "title": "Magazine de bord Air Fast Congo",
                "description": "Magazine public consultable en ligne.",
                "kind": ResourceKind.URL,
                "external_url": "https://airfast-congo.com/inflight-magazine-fra/",
                "visibility": ResourceVisibility.PUBLIC,
                "status": ResourceStatus.PUBLISHED,
                "version": 1,
                "created_by": activity.created_by,
                "published_at": ctx.as_of,
            },
        )
    if any(token in media for token in ("image", "gallery", "poster", "cover", "hero", "badge")):
        _file_resource(ctx, activity=activity, key="demo-image", title=f"Visuel — {activity.title}", filename="image.png", mime="image/png", data=_png_bytes(spec["id"]))
    if "gallery" in media:
        _file_resource(ctx, activity=activity, key="demo-gallery-2", title=f"Galerie — {activity.title}", filename="gallery.png", mime="image/png", data=_png_bytes(spec["id"], 2))
    if "pdf" in media or any(token in media for token in ("receipt", "ticket_demo", "contract", "rules", "brochure", "checklist", "manual", "invoice", "award")):
        _file_resource(ctx, activity=activity, key="demo-pdf", title=f"Guide et informations — {activity.title}", filename="document.pdf", mime="application/pdf", data=_pdf_bytes(spec))
    if "xlsx" in media:
        _file_resource(ctx, activity=activity, key="demo-xlsx", title=f"Tableau de suivi — {activity.title}", filename="tableur.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", data=_zip_doc("xlsx", spec))
    if "docx" in media:
        _file_resource(ctx, activity=activity, key="demo-docx", title=f"Note de préparation — {activity.title}", filename="document.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", data=_zip_doc("docx", spec))
    if "audio" in media:
        _file_resource(ctx, activity=activity, key="demo-audio", title=f"Note audio — {activity.title}", filename="audio.wav", mime="audio/wav", data=_wav_bytes())
    if "video" in media:
        _file_resource(ctx, activity=activity, key="demo-video", title=f"Présentation vidéo — {activity.title}", filename="video.mp4", mime="video/mp4", data=base64.b64decode(_MP4_DEMO_B64))
    if index % 6 == 0:
        csv = (
            "titre,lieu,annee,situation\n"
            f"{spec['title'].replace(',', ' ')},{spec.get('geo', '').replace(',', ' ')},{spec['year']},"
            f"{STATE_LABELS.get(spec.get('state'), spec.get('state', 'à suivre'))}\n"
        ).encode()
        _file_resource(ctx, activity=activity, key="demo-csv", title=f"Données de suivi — {activity.title}", filename="donnees.csv", mime="text/csv", data=csv)


def _seed_events(ctx, specs, *, space, actor, places, activities, occurrences):
    category = upsert(EventCategory, "mobile-mature-category", defaults={"name": "Rencontres et expériences", "slug": "mobile-mature-experiences", "description": "Conférences, ateliers, culture et rencontres.", "is_active": True})
    online = upsert(EventVenue, "mobile-mature-online", defaults={"name": "En ligne", "kind": VenueKind.ONLINE, "online_url": "https://www.undp.org/fr/careers", "is_active": True})
    venue_cache = {}
    for index, spec in enumerate(specs):
        place = _place_for(spec, places)
        activity = _activity(spec, vertical="event", space=space, actor=actor)
        occurrence = _occurrence(ctx, spec, activity=activity, place=place, index=index)
        venue = online
        if place:
            venue = venue_cache.get(place.pk)
            if not venue:
                venue = upsert(EventVenue, f"mobile-mature-venue-{place.pk}", defaults={"name": f"Espace central — {place.name}", "kind": VenueKind.PHYSICAL, "place": place, "is_active": True})
                venue_cache[place.pk] = venue
        event = upsert(
            Event,
            f"mobile-mature-event-{spec['id']}",
            defaults={
                "activity": activity,
                "category": category,
                "venue": venue,
                "slug": f"mobile-mature-{spec['id'].lower()}",
                "published_at": ctx.as_of - timedelta(days=120),
                "metadata": {"seed": SEED_MARKER, "fixture_id": spec["id"], "state": spec["state"], "provenance": spec["provenance"]},
            },
        )
        if not event.cover_image:
            cover_name = event_cover_path(event, f"{spec['id'].lower()}.png")
            stored_name = event.cover_image.storage.save(
                cover_name,
                ContentFile(_png_bytes(spec["id"])),
            )
            Event.objects.filter(pk=event.pk).update(cover_image=stored_name)
            event.refresh_from_db(fields=["cover_image"])
        _seed_resources(ctx, activity, spec, index)
        activities[spec["id"]] = activity
        occurrences[spec["id"]] = occurrence


def _route_places(spec, places):
    raw = spec["geo"].replace("International", "Johannesburg→Montréal")
    if "→" in raw:
        left, right = [part.strip().lower() for part in raw.split("→", 1)]
        if left in PLACE_ALIASES and right in PLACE_ALIASES:
            return places[PLACE_ALIASES[left]], places[PLACE_ALIASES[right]]
    if spec["id"] in {"TRN-006", "TRN-018"}:
        return places["lubumbashi_airport"], places["lubumbashi"]
    place = _place_for(spec, places) or places["lubumbashi"]
    return place, places["lubumbashi_airport"] if place.pk != places["lubumbashi_airport"].pk else places["lubumbashi"]


def _seed_transport(ctx, specs, *, space, actor, places, activities, occurrences):
    road = upsert(Vehicle, "mobile-mature-road", defaults={"space": space, "label": "Autocar Horizon 52", "registration": "", "vehicle_type": VehicleType.BUS, "passenger_capacity": 52, "active": True})
    air = upsert(Vehicle, "mobile-mature-air", defaults={"space": space, "label": "Navette régionale Horizon", "registration": "", "vehicle_type": VehicleType.OTHER, "passenger_capacity": 120, "active": True})
    for index, spec in enumerate(specs):
        origin, destination = _route_places(spec, places)
        mode = TransportMode.AIR if origin.country_code != destination.country_code or origin.locality in {"Kinshasa", "Kamina", "Kalemie"} or destination.locality in {"Kinshasa", "Kamina", "Kalemie"} else TransportMode.ROAD
        route = upsert(TransportRoute, f"mobile-mature-route-{spec['id']}", defaults={"space": space, "code": spec["id"], "name": f"{origin.name} → {destination.name}", "active": True})
        TransportRouteStop.objects.update_or_create(route=route, position=1, defaults={"place": origin, "boarding_allowed": True, "alighting_allowed": False})
        TransportRouteStop.objects.update_or_create(route=route, position=2, defaults={"place": destination, "boarding_allowed": False, "alighting_allowed": True})
        activity = _activity(spec, vertical="transport", space=space, actor=actor)
        upsert(TransportService, f"mobile-mature-transport-{spec['id']}", defaults={"activity": activity, "route": route, "mode": mode})
        occurrence = _occurrence(ctx, spec, activity=activity, place=origin, index=index)
        vehicle = air if mode == TransportMode.AIR else road
        pool = upsert(CapacityPool, f"mobile-mature-capacity-{spec['id']}", defaults={"activity": activity, "occurrence": occurrence, "label": "Voyageurs", "total_quantity": min(vehicle.passenger_capacity, 80), "is_active": True})
        upsert(TransportDeparture, f"mobile-mature-departure-{spec['id']}", defaults={"occurrence": occurrence, "vehicle": vehicle, "passenger_capacity_pool": pool, "boarding_instructions": "Présenter un accès valide si requis.", "operational_reference": spec["id"]})
        _seed_resources(ctx, activity, spec, index)
        activities[spec["id"]] = activity
        occurrences[spec["id"]] = occurrence


SERVICE_KINDS = (ServiceKind.ADMINISTRATIVE_SUPPORT, ServiceKind.DOCUMENT_SUPPORT, ServiceKind.CAREER_SUPPORT, ServiceKind.EDUCATION_GUIDANCE, ServiceKind.INTERVIEW_PREPARATION, ServiceKind.ORIENTATION, ServiceKind.OTHER)


def _seed_services(ctx, specs, *, space, actor, places, activities, occurrences):
    for index, spec in enumerate(specs):
        activity = _activity(spec, vertical="service", space=space, actor=actor)
        upsert(ServiceDetails, f"mobile-mature-service-{spec['id']}", defaults={"activity": activity, "service_kind": SERVICE_KINDS[index % len(SERVICE_KINDS)]})
        occurrence = _occurrence(ctx, spec, activity=activity, place=_place_for(spec, places), index=index)
        _seed_resources(ctx, activity, spec, index)
        activities[spec["id"]] = activity
        occurrences[spec["id"]] = occurrence


def _seed_funding(ctx, specs, *, space, actor, places, activities, occurrences):
    for index, spec in enumerate(specs):
        activity = _activity(spec, vertical="funding", space=space, actor=actor)
        pivot = _scheduled_at(ctx, spec, index)
        upsert(
            FundingDetails,
            f"mobile-mature-funding-{spec['id']}",
            defaults={
                "activity": activity,
                "currency": "USD",
                "target_amount": Decimal(str(1000 + 250 * index)),
                "minimum_contribution": Decimal("10.00"),
                "maximum_contribution": Decimal("500.00"),
                "opens_at": pivot - timedelta(days=45),
                "closes_at": pivot + (timedelta(days=75) if spec["state"] not in TERMINAL_STATES else timedelta(days=1)),
            },
        )
        occurrence = _occurrence(ctx, spec, activity=activity, place=_place_for(spec, places), index=index)
        _seed_resources(ctx, activity, spec, index)
        activities[spec["id"]] = activity
        occurrences[spec["id"]] = occurrence


OPPORTUNITY_KINDS = (OpportunityKind.PROGRAM, OpportunityKind.SCHOLARSHIP, OpportunityKind.JOB, OpportunityKind.EDUCATION, OpportunityKind.GRANT, OpportunityKind.COMPETITION, OpportunityKind.INTERNSHIP, OpportunityKind.OTHER)


def _opportunity_summary(spec: dict) -> str:
    relation = RELATION_LABELS.get(spec.get("relation"), "à explorer")
    state = STATE_LABELS.get(spec.get("state"), "à suivre")
    return (
        f"{spec['title']} est une possibilité {relation} dans le parcours d’Alain. "
        f"Elle est rattachée à {spec.get('geo') or 'un contexte à confirmer'} et apparaît actuellement comme {state}."
    )


def _seed_opportunities(ctx, specs, *, curator, primary):
    for index, spec in enumerate(specs):
        kind = OPPORTUNITY_KINDS[index % len(OPPORTUNITY_KINDS)]
        opportunity = upsert(Opportunity, f"mobile-mature-opportunity-{spec['id']}", defaults={"kind": kind, "created_by": curator})
        pivot = _scheduled_at(ctx, spec, index)
        revision = upsert(
            OpportunityRevision,
            f"mobile-mature-opportunity-revision-{spec['id']}",
            defaults={
                "opportunity": opportunity,
                "version": 1,
                "title": spec["title"],
                "summary": _opportunity_summary(spec),
                "issuer_name": ISSUERS[index % len(ISSUERS)],
                "opens_at": pivot - timedelta(days=30),
                "deadline_at": pivot + (timedelta(days=90) if spec["state"] not in TERMINAL_STATES else timedelta(days=1)),
                "timezone": "Africa/Lubumbashi",
                "application_instructions": "Vérifier les conditions, préparer les pièces utiles et suivre la candidature depuis Makolo.",
                "remote_allowed": index % 3 == 0,
                "created_by": curator,
            },
        )
        public_url = PUBLIC_SOURCES.get(spec["provenance"])
        directory_name, directory_url = OPPORTUNITY_DIRECTORY_URLS[kind]
        upsert(
            OpportunitySource,
            f"mobile-mature-opportunity-source-{spec['id']}",
            defaults={
                "opportunity": opportunity,
                "source_type": OpportunitySourceType.OFFICIAL if public_url else OpportunitySourceType.AGGREGATOR,
                "source_name": PUBLIC_SOURCE_LABELS.get(spec["provenance"], directory_name),
                "url": public_url or directory_url,
                "external_reference": f"mobile-mature:{spec['id']}",
                "is_primary": True,
                "status": OpportunitySourceStatus.ACTIVE,
                "discovered_at": ctx.as_of - timedelta(days=30),
                "last_checked_at": ctx.as_of - timedelta(days=1),
                "verified_at": ctx.as_of - timedelta(days=1) if public_url else None,
                "verified_by": curator if public_url else None,
            },
        )
        if revision.published_at is None:
            revision.published_at = ctx.as_of - timedelta(days=20)
            revision._allow_publication = True
            revision.save(update_fields=["published_at"])
        Opportunity.objects.filter(pk=opportunity.pk).update(publication_status=OpportunityPublicationStatus.PUBLISHED, current_revision=revision, published_at=ctx.as_of - timedelta(days=20))
        if spec["relation"] in {"saved", "watched", "engaged", "draft", "planned"}:
            OpportunitySave.objects.get_or_create(profile=primary, opportunity=opportunity)


MODE_CYCLE = (ObtentionModeCode.BUY, ObtentionModeCode.RENT, ObtentionModeCode.BORROW, ObtentionModeCode.RECEIVE, ObtentionModeCode.EXCHANGE)


def _seed_obtentions(ctx, specs, *, space, actor, primary, places, activities, occurrences, obtentions):
    for index, spec in enumerate(specs):
        existing = ObtentionDetails.objects.select_related("activity").filter(activity__space=space, activity__slug=f"mobile-mature-{spec['id'].lower()}").first()
        if existing is None:
            existing = create_obtention(
                actor=actor,
                space=space,
                title=spec["title"],
                short_description=f"{spec['title']} — {RELATION_LABELS.get(spec.get('relation'), 'à suivre')}.",
                description=(
                    f"{spec['title']} fait partie des choses qu’Alain souhaite acheter, louer, emprunter ou recevoir. "
                    f"Makolo suit la remise effective ou le droit d’usage, indépendamment du paiement."
                ),
                targets=[{"title": spec["title"], "quantity": "1", "unit": "unité"}],
                modes=[MODE_CYCLE[index % len(MODE_CYCLE)]],
                result_label="Cible effectivement remise ou droit d'usage effectivement acquis",
                status=ActivityStatus.PUBLISHED,
                visibility=ActivityVisibility.PUBLIC,
            )
            existing.activity.slug = f"mobile-mature-{spec['id'].lower()}"
            existing.activity.save(update_fields=["slug", "updated_at"])
        activity = existing.activity
        # Keep Obtention enterable until the beneficiary Journey has been
        # created through the canonical service. Historical closure is applied
        # after personal relations are seeded.
        occurrence = _occurrence(ctx, spec, activity=activity, place=_place_for(spec, places), index=index)
        _seed_resources(ctx, activity, spec, index)
        activities[spec["id"]] = activity
        occurrences[spec["id"]] = occurrence
        obtentions[spec["id"]] = existing
        if spec["relation"] in {"saved", "watched", "discover_only"}:
            ActivityBookmark.objects.get_or_create(user=primary, activity=activity)


def _journey_status(spec):
    if spec["relation"] in {"completed", "experienced"} or spec["state"] in {"completed", "fulfilled", "returned"}:
        return JourneyStatus.FULFILLED
    if spec["relation"] in {"rejected", "not_eligible"}:
        return JourneyStatus.REJECTED
    if spec["relation"] in {"abandoned", "declined"} or spec["state"] == "cancelled":
        return JourneyStatus.CANCELLED
    if spec["state"] == "expired":
        return JourneyStatus.EXPIRED
    if spec["relation"] in {"engaged", "space_context", "draft", "planned", "invited"}:
        return JourneyStatus.IN_PROGRESS
    return JourneyStatus.CONFIRMED


WORKFLOW = {"event": WorkflowKind.REGISTRATION, "transport": WorkflowKind.RESERVATION, "service": WorkflowKind.SERVICE, "funding": WorkflowKind.FULFILLMENT}


def _generic_journey(ctx, *, primary, vertical, spec, activity, occurrence):
    status = _journey_status(spec)
    pivot = _scheduled_at(ctx, spec, 1)
    submitted = min(ctx.as_of - timedelta(days=30), pivot - timedelta(days=2))
    journey = upsert(
        Journey,
        f"mobile-mature-journey-{spec['id']}",
        defaults={
            "initiated_by": primary,
            "beneficiary": primary,
            "activity": activity,
            "occurrence": occurrence,
            "workflow": WORKFLOW[vertical],
            "status": status,
            "submitted_at": submitted,
            "confirmed_at": submitted + timedelta(hours=1),
            "started_at": submitted + timedelta(days=1),
            "fulfilled_at": ctx.as_of - timedelta(days=1) if status == JourneyStatus.FULFILLED else None,
            "cancelled_at": ctx.as_of - timedelta(days=1) if status == JourneyStatus.CANCELLED else None,
        },
    )
    if vertical == "service":
        ServiceJourneyContext.objects.get_or_create(journey=journey, defaults={"objective": f"Faire avancer {spec['title']} jusqu’à son résultat utile."})
    if int(spec["year"]) < MATRIX_REFERENCE_YEAR:
        backdate(journey, created_at=pivot - timedelta(days=14), updated_at=pivot)
    return journey


def _seed_personal_relations(ctx, *, primary, activities, occurrences, obtentions):
    for vertical in ("event", "transport", "service", "funding", "obtention"):
        for spec in REALITY_SPECS[vertical]:
            if spec["relation"] in {"saved", "watched", "discover_only"}:
                ActivityBookmark.objects.get_or_create(user=primary, activity=activities[spec["id"]])

    journeys = []
    for vertical in ("event", "transport", "service", "funding"):
        historical = [spec for spec in REALITY_SPECS[vertical] if int(spec["year"]) < MATRIX_REFERENCE_YEAR and spec["relation"] in {"completed", "experienced", "abandoned", "rejected"}][:4]
        active = [spec for spec in REALITY_SPECS[vertical] if int(spec["year"]) == MATRIX_REFERENCE_YEAR and spec["relation"] in {"engaged", "space_context", "draft", "invited"}][:4]
        for spec in historical + active:
            journeys.append(_generic_journey(ctx, primary=primary, vertical=vertical, spec=spec, activity=activities[spec["id"]], occurrence=occurrences.get(spec["id"])))

    obtention_specs = (
        [spec for spec in REALITY_SPECS["obtention"] if int(spec["year"]) < MATRIX_REFERENCE_YEAR and spec["relation"] == "completed"][:4]
        + [spec for spec in REALITY_SPECS["obtention"] if int(spec["year"]) == MATRIX_REFERENCE_YEAR and spec["relation"] == "engaged"][:4]
    )
    for spec in obtention_specs:
        obtention = obtentions[spec["id"]]
        existing = Journey.objects.filter(beneficiary=primary, activity=obtention.activity, obtention_context__isnull=False).first()
        if existing is None:
            configuration = obtention.configurations.filter(status="published").prefetch_related("modes").first()
            mode = configuration.modes.order_by("position", "id").first()
            existing = create_obtention_journey(obtention=obtention, actor=primary, beneficiary=primary, mode=mode, occurrence=occurrences.get(spec["id"]))
            existing = activate_obtention_journey(journey=existing, actor=primary)
        target = _journey_status(spec)
        if existing.status != target:
            values = {"status": target}
            if target == JourneyStatus.FULFILLED:
                values["fulfilled_at"] = ctx.as_of - timedelta(days=1)
            Journey.objects.filter(pk=existing.pk).update(**values)
            existing.refresh_from_db()
        journeys.append(existing)

    actionable = [j for j in journeys if j.status in {JourneyStatus.CONFIRMED, JourneyStatus.IN_PROGRESS}][:5]
    for position, journey in enumerate(actionable, 1):
        JourneyStep.objects.get_or_create(
            pk=stable_uuid(f"mobile-mature-step-{journey.pk}"),
            defaults={
                "journey": journey,
                "kind": JourneyStepKind.ACTION,
                "title": f"Vérifier la prochaine étape — {journey.activity.title}",
                "description": "Confirmer ce qui est prêt, ce qui manque et l’action qui peut réellement être faite maintenant.",
                "status": JourneyStepStatus.READY,
                "position": position * 10,
                "is_required": True,
                "due_at": ctx.as_of + timedelta(hours=position * 3),
                "origin": JourneyStepOrigin.MANUAL,
                "created_by": primary,
                "status_changed_by": primary,
                "status_reason": "mobile_mature_demo",
            },
        )


def seed_mobile_mature_universe(ctx: SeedContext) -> User:
    """Seed a dense canonical server universe for Flutter development.

    The function deliberately creates facts, not relevance scores. Existing
    projections/APIs remain responsible for sending these facts to mobile.
    """

    primary = _principal(ctx)
    owner = User.objects.get(email=BETA_PERSONAS["space_admin"])
    curator = User.objects.get(email=BETA_PERSONAS["staff"])
    spaces = _providers(owner)
    places = _places(owner)
    activities, occurrences, obtentions = {}, {}, {}

    _seed_events(ctx, REALITY_SPECS["event"], space=spaces["event"], actor=owner, places=places, activities=activities, occurrences=occurrences)
    _seed_transport(ctx, REALITY_SPECS["transport"], space=spaces["transport"], actor=owner, places=places, activities=activities, occurrences=occurrences)
    _seed_services(ctx, REALITY_SPECS["service"], space=spaces["service"], actor=owner, places=places, activities=activities, occurrences=occurrences)
    _seed_funding(ctx, REALITY_SPECS["funding"], space=spaces["funding"], actor=owner, places=places, activities=activities, occurrences=occurrences)
    _seed_opportunities(ctx, REALITY_SPECS["opportunity"], curator=curator, primary=primary)
    _seed_obtentions(ctx, REALITY_SPECS["obtention"], space=spaces["obtention"], actor=owner, primary=primary, places=places, activities=activities, occurrences=occurrences, obtentions=obtentions)
    _seed_personal_relations(ctx, primary=primary, activities=activities, occurrences=occurrences, obtentions=obtentions)

    # Historical Obtention can only be closed after its Journey exists: the
    # canonical entry service correctly rejects non-published Activities.
    for spec in REALITY_SPECS["obtention"]:
        activity = activities[spec["id"]]
        target_status = _activity_status(spec)
        if activity.status != target_status:
            activity.status = target_status
            activity._allow_status_transition = True
            activity.save(update_fields=["status", "updated_at"])

    for vertical, specs in REALITY_SPECS.items():
        ctx.add(f"mobile_mature_{vertical}_items", len(specs))
    ctx.add("mobile_mature_resources", ActivityResource.objects.filter(activity__slug__startswith="mobile-mature-").count())
    ctx.add("mobile_mature_journeys", Journey.objects.filter(beneficiary=primary, activity__slug__startswith="mobile-mature-").count())
    return primary
