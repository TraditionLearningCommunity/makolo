"""Makolo conversations demo: contextual Points, decisions and exchanges.

One existing SQLite beta DB, no new Profile or business table. All mutations
pass through canonical Conversations services and scoped authorization.
Dates of linked Occurrences define the scenario phase; audit timestamps are
never forged. DIRECT requires real bilateral consent and is not auto-seeded.
"""
import argparse
import hashlib
import random
from collections import Counter
from datetime import timedelta


def phase_for_dates(start, end, now):
    if end is not None and end < now:
        return "past"
    if start is not None and end is not None and start <= now < end:
        return "live"
    if start is not None and start > now:
        return "future"
    return "ongoing"


def point_blueprints(phase, label):
    label = str(label).strip()[:110]
    if phase == "past":
        return (
            ("information", "Bilan de " + label,
             "Cette action est passée. Retrouvons ce qui a été fait et les suites à préparer.", "none", ()),
            ("question", "Retour d'expérience",
             "Qu'est-ce qui a facilité votre démarche, et que faudrait-il améliorer ?", "free_text", ()),
            ("poll", "Priorité pour la suite",
             "Quel sujet mérite d'être traité en premier ?", "single_choice",
             ("Informations", "Organisation", "Accompagnement")),
            ("request", "Suite à donner",
             "Quelle prochaine action serait utile après cette expérience ?", "free_text", ()),
        )
    if phase == "live":
        return (
            ("information", "Coordination en cours : " + label,
             "Le contexte est en cours. Les indications pratiques et les demandes sont regroupées ici.", "none", ()),
            ("confirmation", "Informations reçues",
             "Avez-vous reçu les informations nécessaires pour avancer ?", "boolean", ()),
            ("question", "Besoin immédiat",
             "Quel obstacle concret faut-il résoudre maintenant ?", "free_text", ()),
            ("exchange", "Coordination du moment",
             "Échanges relatifs au déroulement en cours et aux actions à réaliser.", "free_text", ()),
        )
    if phase == "future":
        return (
            ("information", "Préparation : " + label,
             "Ce contexte arrive prochainement. Vérifions ce qui doit être préparé.", "none", ()),
            ("confirmation", "Prêt pour la suite",
             "Avez-vous les informations nécessaires à votre préparation ?", "boolean", ()),
            ("poll", "Point de préparation prioritaire",
             "Sur quoi faut-il concentrer la préparation ?", "single_choice",
             ("Documents", "Transport et accès", "Informations pratiques")),
            ("question", "Question avant le démarrage",
             "Que souhaitez-vous clarifier avant de commencer ?", "free_text", ()),
        )
    return (
        ("information", "Suivi de " + label,
         "Ce Point rassemble les éléments utiles à la coordination de cette action.", "none", ()),
        ("question", "Clarifier les prochaines étapes",
         "Quelle information vous manque pour avancer ?", "free_text", ()),
        ("confirmation", "Besoin d'accompagnement",
         "Souhaitez-vous une précision pour la prochaine étape ?", "boolean", ()),
        ("exchange", "Échange autour de l'action",
         "Coordonnons les suites utiles à ce contexte.", "free_text", ()),
    )



def coherent_reply(phase, label, reference):
    """Stable natural responses anchored to the phase, never a fabricated proof."""
    label = str(label).strip()[:90]
    choices = {
        "past": (
            "Le déroulement était clair. Je voudrais connaître les démarches de suivi.",
            "L'accueil m'a aidé à trouver les informations nécessaires. Une synthèse serait utile.",
            "La prochaine fois, il faudrait communiquer les horaires un peu plus tôt.",
        ),
        "live": (
            "Je suis sur place. Où retrouver les consignes d'accès et d'orientation ?",
            "Je peux poursuivre, mais j'ai besoin d'une précision sur l'étape actuelle.",
            "Je suis disponible pour aider à l'accueil si cela est utile.",
        ),
        "future": (
            "Je vais préparer les informations demandées. Quels documents sont indispensables ?",
            "Je souhaite vérifier l'heure et le lieu avant de confirmer ma participation.",
            "Je peux m'organiser à l'avance si le déroulement prévu est confirmé.",
        ),
        "ongoing": (
            "J'ai pris connaissance des prochaines étapes. Il reste un point à clarifier.",
            "Je voudrais savoir à qui m'adresser pour la suite de cette démarche.",
            "Je peux transmettre les informations demandées après confirmation des modalités.",
        ),
    }
    variants = choices.get(phase, choices["ongoing"])
    variant = int(hashlib.sha256(reference.encode("utf-8")).hexdigest()[:8], 16) % len(variants)
    return variants[variant]


def exchange_dialogue(phase, reference):
    """Question and reply from the same practical situation."""
    choices = {
        "past": ("Peut-on retrouver un récapitulatif des étapes réalisées ?",
                 "Oui, regroupons les informations utiles pour la prochaine démarche."),
        "live": ("Où se trouve le point d'accueil pour la suite ?",
                 "Les indications sont regroupées dans cette Conversation ; vérifions le parcours ensemble."),
        "future": ("Quels éléments devons-nous préparer avant la rencontre ?",
                   "Commençons par vérifier les documents, l'horaire et le lieu annoncés."),
        "ongoing": ("Quelle est la prochaine action concrète à préparer ?",
                    "Identifions d'abord ce qui manque et qui peut apporter une réponse."),
    }
    return choices.get(phase, choices["ongoing"])


def scenario_reference(kind, target_id, phase, index):
    raw = f"demo-conversation-v1:{kind}:{target_id}:{phase}:{index}"
    return "demo-conv-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:44]


def collect_candidates(people, now, limit):
    from django.db.models import Q
    from authorization.constants import PermissionCode
    from authorization.services import can
    from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
    from journeys.models import Journey
    from organizations.models import Organization
    from groups.models import Group
    from objectives.models import Dossier, Project
    from social.models import ActionProposal

    ids = {p.pk for p in people}
    groups = {}
    def add(bucket, kind, field, obj, actor, label, phase):
        if actor is None or actor.pk not in ids:
            return
        groups.setdefault(bucket, []).append((kind, field, obj, actor, label, phase))

    def activity_actor(activity):
        # Space creator is a candidate, never automatically authorized.
        possible = (activity.owner_profile,
                    activity.space.created_by if activity.space_id else None,
                    activity.created_by)
        for person in possible:
            if person is None or person.pk not in ids:
                continue
            if activity.owner_profile_id == person.pk or can(
                person, PermissionCode.ACTIVITY_CONVERSATIONS_MANAGE, activity=activity
            ):
                return person
        return None

    owner_or_space = (
        Q(activity__owner_profile__in=people) |
        Q(activity__space__created_by__in=people) |
        Q(activity__created_by__in=people)
    )
    base = Occurrence.objects.filter(owner_or_space).exclude(
        status=OccurrenceStatus.CANCELLED
    ).select_related(
        "activity", "activity__owner_profile",
        "activity__space", "activity__space__created_by", "activity__created_by",
    )
    for obj in base.filter(start_at__lte=now, end_at__gt=now).order_by("start_at", "id")[:limit]:
        add("live", "occurrence", "occurrence", obj, activity_actor(obj.activity),
            obj.activity.title, "live")
    for obj in base.filter(end_at__lte=now).order_by("-end_at", "id")[:limit]:
        add("past", "occurrence", "occurrence", obj, obj.activity.owner_profile,
            obj.activity.title, "past")
    for obj in base.filter(start_at__gt=now).order_by("start_at", "id")[:limit * 2]:
        add("future", "occurrence", "occurrence", obj, obj.activity.owner_profile,
            obj.activity.title, "future")

    for obj in Activity.objects.filter(
        Q(owner_profile__in=people) | Q(space__created_by__in=people) |
        Q(created_by__in=people),
        status=ActivityStatus.PUBLISHED,
    ).select_related("owner_profile", "space", "space__created_by", "created_by").order_by("id")[:limit]:
        add("activity", "activity", "activity", obj, activity_actor(obj), obj.title, "ongoing")

    for obj in Journey.objects.filter(
        Q(beneficiary__in=people) | Q(initiated_by__in=people),
    ).select_related("beneficiary", "initiated_by", "activity").order_by("-created_at", "id")[:limit]:
        actor = obj.beneficiary if obj.beneficiary_id in ids else obj.initiated_by
        add("journey", "journey", "journey", obj, actor,
            obj.activity.title, "ongoing")

    for obj in Organization.objects.filter(
        created_by__in=people,
    ).select_related("created_by").order_by("id")[:limit]:
        add("space", "space", "space", obj, obj.created_by, obj.name, "ongoing")

    for obj in Group.objects.filter(owner_profile__in=people).select_related(
        "owner_profile").order_by("id")[:limit]:
        add("group", "group", "group", obj, obj.owner_profile, obj.name, "ongoing")

    for model, kind, field in (
        (Dossier, "dossier", "dossier"),
        (Project, "project", "project"),
    ):
        for obj in model.objects.filter(owner_profile__in=people).select_related(
            "owner_profile").order_by("id")[:limit]:
            add(kind, kind, field, obj, obj.owner_profile, obj.title, "ongoing")

    for obj in ActionProposal.objects.filter(
        Q(need__owner_profile__in=people) | Q(candidate_profile__in=people)
    ).select_related("need", "need__owner_profile", "candidate_profile").order_by("id")[:limit]:
        actor = obj.need.owner_profile if obj.need.owner_profile_id in ids else obj.candidate_profile
        add("proposal", "action_proposal", "action_proposal", obj, actor,
            "Proposition d'entraide", "ongoing")
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--count", type=int, default=100,
                        help="Maximum distinct context Conversations (not Points)")
    parser.add_argument("--profiles", type=int, default=30)
    parser.add_argument("--profile-username", default=None)
    parser.add_argument("--include-test-users", action="store_true",
                        help="Include existing beta_* and mobile_mature_* users")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--points", type=int, default=4, choices=(1, 2, 3, 4))
    args = parser.parse_args(argv)
    if not 1 <= args.count <= 2000 or not 1 <= args.profiles <= 100:
        parser.error("count 1..2000, profiles 1..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.db.models import Q
    from django.utils import timezone
    from conversations.core_models import ConversationContextKind, ConversationModePreset, ConversationLifecycle
    from conversations.point_models import (
        ConversationPoint, ConversationPointKind, ConversationPointResponseMode,
    )
    from conversations.services import (
        ensure_context_conversation, can_view_conversation,
        update_personal_conversation_state, transition_conversation,
        activate_participation,
    )
    from conversations.point_services import (
        create_point, submit_point_response, create_exchange_entry,
        point_response_allowed, resolve_point, acknowledge_point,
    )
    from conversations.audience_services import conversation_viewer_ids
    if connection.vendor != "sqlite":
        parser.error("SQLite demo uniquement")
    U = get_user_model()
    queryset = U.objects.filter(is_active=True, is_staff=False, is_superuser=False)
    if args.profile_username:
        queryset = queryset.filter(username=args.profile_username)
    elif args.include_test_users:
        queryset = queryset.filter(
            Q(username__startswith="world_") |
            Q(username__startswith="beta_") |
            Q(username__startswith="mobile_mature_")
        )
    else:
        queryset = queryset.filter(username__startswith="world_")
    people = list(queryset.order_by("username")[:args.profiles])
    if not people:
        parser.error("Aucun profil éligible; aucun utilisateur ne sera créé")
    now = timezone.now()
    # Over-sample and interleave kinds so 500 is not 500 copies of one Event.
    pools = collect_candidates(people, now, max(args.count * 3, 100))
    rng = random.Random(args.seed)
    for values in pools.values():
        rng.shuffle(values)
    buckets = ("live", "future", "past", "journey", "space", "activity",
               "group", "dossier", "project", "proposal")
    selected = []
    seen = set()
    while len(selected) < args.count:
        made_progress = False
        for bucket in buckets:
            candidates = pools.get(bucket, [])
            while candidates:
                item = candidates.pop()
                key = (item[0], str(item[2].pk), item[5])
                if key not in seen:
                    seen.add(key)
                    selected.append(item)
                    made_progress = True
                    break
            if len(selected) >= args.count:
                break
        if not made_progress:
            break
    counts = Counter()
    counts["profiles"] = len(people)
    counts["eligible_contexts"] = sum(len(x) for x in pools.values()) + len(selected)
    counts["selected_contexts"] = len(selected)
    from conversations.models import ConversationContext
    for kind, field, target, actor, label, phase in selected:
        purpose_key = "demo-" + ("bilan" if phase == "past" else
                                 "jour-j" if phase == "live" else
                                 "preparation" if phase == "future" else "coordination")
        lookup = {"kind": kind, field: target, "purpose_key": purpose_key}
        existing = ConversationContext.objects.filter(**lookup).select_related("conversation").first()
        if not args.apply:
            counts["conversations_existing" if existing else "conversations_planned"] += 1
            if existing:
                counts["points_existing"] += ConversationPoint.objects.filter(
                    conversation=existing.conversation).count()
            else:
                counts["points_planned"] += args.points
            counts["phase_" + phase] += 1
            continue
        try:
            with transaction.atomic():
                phase_label = {
                    "past": "Bilan", "live": "Coordination en cours",
                    "future": "Préparation", "ongoing": "Suivi",
                }.get(phase, "Suivi")
                phase_purpose = {
                    "past": "Faire le point après ",
                    "live": "Coordonner les actions en cours pour ",
                    "future": "Préparer les étapes et questions avant ",
                    "ongoing": "Suivre les échanges et les prochaines étapes de ",
                }.get(phase, "Suivre les étapes de ")
                conversation = ensure_context_conversation(
                    actor=actor, kind=kind, purpose_key=purpose_key,
                    title_override=(label[:160] + " — " + phase_label)[:220],
                    purpose=(phase_purpose + label[:200])[:500],
                    separation_reason=phase_label,
                    mode_preset=ConversationModePreset.MIXED,
                    **{field: target},
                )
                counts["conversations_existing" if existing else "conversations_created"] += 1
                if conversation.lifecycle != ConversationLifecycle.OPEN:
                    counts["closed_conversations_preserved"] += 1
                    continue
                # Explicitly materialize only participants already granted
                # contextual viewing rights by the canonical audience selector.
                eligible = conversation_viewer_ids(conversation) - {actor.pk}
                demo_participants = list(U.objects.filter(
                    pk__in=eligible, is_active=True, is_staff=False, is_superuser=False,
                    username__startswith="world_",
                ).order_by("username")[:3])
                for participant in demo_participants:
                    activate_participation(
                        actor=actor, conversation=conversation, profile=participant,
                    )
                    counts["participations_ensured"] += 1
                refs = point_blueprints(phase, label)[:args.points]
                for index, (point_kind, title, body, response_mode, options) in enumerate(refs):
                    ref = scenario_reference(kind, target.pk, phase, index)
                    if ConversationPoint.objects.filter(client_reference=ref).exists():
                        counts["points_existing"] += 1
                        continue
                    try:
                        # A failed answer/resolution cannot roll back unrelated
                        # valid Points of the same Conversation.
                        with transaction.atomic():
                            point = create_point(
                                actor=actor, conversation=conversation,
                                kind=point_kind, title=title[:220], body=body,
                                response_mode=response_mode,
                                options=options, client_reference=ref,
                            )
                        counts["points_created"] += 1
                    except (PermissionDenied, ValidationError) as exc:
                        counts["points_rejected"] += 1
                        if counts["points_rejected"] <= 5:
                            print("POINT_REJECTED", kind, type(exc).__name__, str(exc)[:160])
                        continue
                    viewers = conversation_viewer_ids(conversation) - {actor.pk}
                    # A targeted Profile may converse with *other* existing
                    # synthetic users already eligible in this context.
                    # Never impersonate arbitrary beta/real users.
                    respondent = next((
                        person for person in U.objects.filter(
                            pk__in=viewers, is_active=True, is_staff=False,
                            is_superuser=False,
                        ).filter(
                            Q(username__startswith="world_") |
                            Q(username__startswith="beta_") |
                            Q(username__startswith="mobile_mature_")
                        ).order_by("username")
                        if point_response_allowed(person, point)
                    ), None)
                    try:
                        with transaction.atomic():
                            if respondent and point_kind == ConversationPointKind.EXCHANGE:
                                first_entry = create_exchange_entry(actor=respondent, point=point,
                                    body=exchange_dialogue(phase, ref)[0],
                                    client_reference=ref + "-entry")
                                counts["exchanges_created"] += 1
                                create_exchange_entry(actor=actor, point=point,
                                    body=exchange_dialogue(phase, ref)[1],
                                    reply_to=first_entry, client_reference=ref + "-reply-entry")
                                counts["exchange_replies_created"] += 1
                            elif respondent and response_mode != ConversationPointResponseMode.NONE:
                                if response_mode == ConversationPointResponseMode.BOOLEAN:
                                    value = (int(ref[-2:], 16) % 2 == 0)
                                elif response_mode == ConversationPointResponseMode.SINGLE_CHOICE:
                                    choices = list(point.options.order_by("position"))
                                    value = str(choices[int(ref[-2:], 16) % len(choices)].pk)
                                else:
                                    value = coherent_reply(phase, label, ref)
                                submit_point_response(actor=respondent, point=point, value=value,
                                    client_reference=ref + "-reply")
                                counts["responses_created"] += 1
                            if respondent and point.requires_acknowledgement:
                                acknowledge_point(actor=respondent, point=point)
                                counts["acknowledgements_created"] += 1
                            if phase == "past" and respondent and point_kind in {
                                ConversationPointKind.QUESTION, ConversationPointKind.REQUEST,
                            }:
                                resolve_point(actor=actor, point=point,
                                    summary="Les retours sur " + label[:140] + " ont été examinés pour préparer la suite.")
                                counts["resolutions_created"] += 1
                    except (PermissionDenied, ValidationError):
                        counts["responses_or_resolutions_rejected"] += 1
                if can_view_conversation(actor, conversation):
                    update_personal_conversation_state(
                        actor=actor, conversation=conversation, opened=True)
                if phase == "past":
                    transition_conversation(
                        actor=actor, conversation=conversation,
                        lifecycle=ConversationLifecycle.CLOSED,
                    )
                    counts["historical_conversations_closed"] += 1
                counts["phase_" + phase] += 1
        except (PermissionDenied, ValidationError) as exc:
            counts["rejected"] += 1
            if counts["rejected"] <= 8:
                print("CONVERSATION_REJECTED", kind, type(exc).__name__, str(exc)[:240])
    print("CONVERSATIONS", "APPLY" if args.apply else "PREVIEW",
          dict(sorted(counts.items())))
    print("No synthetic Profile, delegated authority, arbitrary DIRECT contact or forged audit timestamp.")


if __name__ == "__main__":
    main()
