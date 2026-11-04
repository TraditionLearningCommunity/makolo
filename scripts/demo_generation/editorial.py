"""Editorial vocabulary for synthetic Makolo data.

Identity is expressed through canonical model ownership, never by appending
usernames or DEMO to public titles. Internal slugs/keys preserve provenance.
All choices are deterministic to support idempotent seed runs.
"""
from hashlib import sha256


def choice(values, *parts):
    raw = ":".join(str(p) for p in parts)
    index = int.from_bytes(sha256(raw.encode("utf-8")).digest()[:8], "big")
    return values[index % len(values)]


SPACE_STEMS = (
    "Collectif Horizon", "Atelier des Possibles", "Maison des Initiatives",
    "Réseau Nouvelle Étape", "Carrefour des Savoirs", "Passerelle Locale",
    "Élan Commun", "Espace Trajectoires", "Maison du Partage",
    "Cercle des Projets", "Point de Rencontre", "Alliance des Talents",
    "Agora des Actions", "Maison des Parcours", "Collectif Perspectives",
)
SPACE_FOCI = (
    "Formation", "Solidarité", "Entrepreneuriat", "Culture",
    "Éducation", "Services", "Mobilité", "Familles", "Innovation",
    "Vie locale", "Jeunesse", "Artisanat", "Accompagnement",
)


def space_name(owner):
    return choice(SPACE_STEMS, "space-stem", owner.pk) + " — " + choice(
        SPACE_FOCI, "space-focus", owner.pk)


def group_name(owner):
    theme = choice((
        "l'entraide de proximité", "les démarches administratives",
        "la préparation des événements", "l'orientation professionnelle",
        "les projets éducatifs", "la mobilité quotidienne",
        "les initiatives associatives", "l'organisation des études",
        "l'entrepreneuriat local", "la formation pratique",
        "les activités culturelles", "l'accompagnement des familles",
    ), "group", owner.pk)
    return "Groupe autour de " + theme


def objective_titles(owner):
    focus = choice((
        "un parcours de formation", "une activité collective",
        "une demande de service", "un projet éducatif",
        "une initiative locale", "un dossier administratif",
        "une participation à un événement", "un changement professionnel",
        "un projet associatif", "une démarche d'obtention",
    ), "objective", owner.pk)
    return ("Préparer " + focus, "Développer " + focus)


_ACTIVITY_THEMES = {
    "funding": (
        "Soutien aux fournitures scolaires", "Bourses de proximité",
        "Appui à la formation professionnelle", "Solidarité pour les études",
        "Initiatives pour les jeunes", "Accompagnement éducatif",
        "Soutien à l'apprentissage", "Équipement pédagogique",
        "Aide à la mobilité scolaire", "Fonds d'initiatives locales",
    ),
    "services": (
        "Accompagnement administratif", "Préparation d'un dossier",
        "Orientation vers les services", "Conseil pour les démarches",
        "Appui aux inscriptions", "Atelier de documents",
        "Accompagnement aux demandes", "Aide à la préparation",
        "Information aux usagers", "Conseil et suivi de dossier",
    ),
    "obtention": (
        "Distribution de kits scolaires", "Accès aux fournitures",
        "Remise de matériel éducatif", "Acquisition de supports d'étude",
        "Fournitures pour la rentrée", "Équipement des apprenants",
        "Accès aux kits d'apprentissage", "Soutien matériel aux élèves",
        "Obtention de matériel scolaire", "Appui à la rentrée scolaire",
    ),
}
_ACTIVITY_CONTEXTS = (
    "de proximité", "dans le quartier", "pour les familles",
    "pour les apprenants", "en milieu associatif", "à Lubumbashi",
    "pour la communauté", "en petits groupes", "pour les nouveaux inscrits",
    "en accompagnement individuel",
)


def activity_title(domain, index):
    bases = _ACTIVITY_THEMES[domain]
    return bases[index % len(bases)] + " " + _ACTIVITY_CONTEXTS[
        (index // len(bases)) % len(_ACTIVITY_CONTEXTS)]


def space_activity_title(owner):
    return choice((
        "Atelier de préparation collective", "Rencontre d'orientation",
        "Séance d'information pratique", "Initiation aux démarches",
        "Atelier de coopération", "Rencontre entre membres",
        "Session de partage de savoirs", "Atelier d'accompagnement",
    ), "space-activity", owner.pk)


def submission_title(opportunity):
    revision = getattr(opportunity, "current_revision", None)
    title = getattr(revision, "title", None) or getattr(opportunity, "title", None)
    return str(title or "Une opportunité à examiner")[:180]
