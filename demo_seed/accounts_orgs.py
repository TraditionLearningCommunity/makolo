from __future__ import annotations

from datetime import time, timedelta

from accounts.models import (
    NotificationPreference,
    PermissionGroup,
    Role,
    User,
    UserActivity,
    UserDevice,
    UserProfile,
    UserSession,
    VerificationDocument,
)
from organizations.models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    OrganizationRole,
    OrganizationVerificationStatus,
)

from .common import SeedContext, backdate, choose, dt, stable_token, upsert


FIRST_NAMES = [
    "Amina", "Grâce", "Sarah", "Naomi", "Déborah", "Esther", "Ruth", "Merveille",
    "Junior", "Patrick", "David", "Joël", "Jonathan", "Samuel", "Chris", "Daniel",
    "Prisca", "Nadine", "Stéphanie", "Chadrack", "Kevin", "Mike", "Trésor", "Fabrice",
    "Carine", "Gloria", "Ben", "Christian", "Cédric", "Divine", "Rebecca", "Arnold",
    "Bénédicte", "Landry", "Lydia", "Moïse", "Israël", "Gloire", "Michaël", "Dorcas",
]
LAST_NAMES = [
    "Kabongo", "Ilunga", "Mutombo", "Kasongo", "Mbuyi", "Kalala", "Mukendi",
    "Tshibangu", "Kanku", "Mwamba", "Kabila", "Lukusa", "Mwamba", "Kalonji",
    "Banza", "Kitenge", "Mwepu", "Kaseya", "Ntumba", "Katanga", "Mbayo",
]
CITIES = [
    ("Lubumbashi", "CD", -11.6647, 27.4794),
    ("Kinshasa", "CD", -4.3250, 15.3222),
    ("Kolwezi", "CD", -10.7167, 25.4667),
    ("Likasi", "CD", -10.9814, 26.7333),
    ("Goma", "CD", -1.6792, 29.2228),
    ("Kisangani", "CD", 0.5153, 25.1910),
]


def seed_accounts_and_organizations(ctx: SeedContext) -> None:
    roles = {}
    for priority, (code, name, description) in enumerate([
        ("participant", "Participant", "Découvre, réserve et utilise des billets."),
        ("organizer", "Organisateur", "Crée et pilote des événements."),
        ("scanner", "Agent scanner", "Contrôle l'accès aux événements."),
        ("platform_ops", "Operations Makolo", "Supervision de la plateforme."),
    ], start=10):
        role = upsert(Role, code, defaults={
            "name": name,
            "code": code,
            "description": description,
            "priority": priority,
            "is_system": True,
            "is_active": True,
        })
        roles[code] = role

    groups = {}
    for code, name, role_codes in [
        ("participants", "Participants", ["participant"]),
        ("organizers", "Organisateurs", ["organizer"]),
        ("access-team", "Équipe accès", ["scanner"]),
        ("platform-operations", "Operations plateforme", ["platform_ops"]),
    ]:
        group = upsert(PermissionGroup, code, defaults={
            "name": name,
            "code": code,
            "description": f"Groupe système de démonstration : {name}.",
        })
        group.roles.set([roles[item] for item in role_codes])
        groups[code] = group

    user_count = ctx.cfg["users"]
    base_date = dt(2024, 1, 8, 8)
    ctx.users.clear()

    for i in range(user_count):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 7) % len(LAST_NAMES)]
        city, country, lat, lon = CITIES[i % len(CITIES)]
        email = f"demo.user{i+1:03d}@makolo.test"
        joined = base_date + timedelta(days=(i * 11) % 910, hours=i % 9)
        is_staff = i < 3
        is_organizer = i < 16
        is_scanner = 10 <= i < 24 or i in {1, 2}
        user = upsert(User, f"user-{i+1:03d}", defaults={
            "email": email,
            "username": f"demo{i+1:03d}",
            "first_name": first,
            "last_name": last,
            "phone": f"+243 97 {1000000+i:07d}",
            "birth_date": dt(1988 + (i % 15), 1 + (i % 12), 1 + (i % 27)).date(),
            "gender": "female" if i % 2 == 0 else "male",
            "bio": f"{first} {last}, membre de la communauté événementielle Makolo à {city}.",
            "language": "fr",
            "timezone": "Africa/Lubumbashi" if city != "Kinshasa" else "Africa/Kinshasa",
            "is_active": True,
            "is_staff": is_staff,
            "is_superuser": i == 0,
            "is_verified": i % 6 != 5,
            "email_verified": i % 8 != 7,
            "phone_verified": i % 4 == 0,
            "is_organizer": is_organizer,
            "is_scanner_agent": is_scanner,
            "onboarding_completed": i % 9 != 8,
            "onboarding_step": 5 if i % 9 != 8 else (i % 5),
            "last_seen": ctx.as_of - timedelta(hours=(i * 3) % 300),
            "last_login_ip": f"10.24.{i % 16}.{10 + (i % 200)}",
            "failed_login_attempts": 2 if i % 31 == 0 else 0,
            "account_locked_until": None,
            "require_2fa": is_staff or i % 17 == 0,
            "website": f"https://example.com/profiles/{i+1}" if i % 7 == 0 else "",
            "instagram_url": f"https://instagram.com/demo_makolo_{i+1}" if i % 5 == 0 else "",
            "metadata": {"seed": "makolo-demo", "city": city, "customer_segment": choose(["regular", "vip", "student", "corporate"], i)},
            "preferences": {"event_categories": choose([["music", "culture"], ["business", "tech"], ["community", "sports"]], i)},
            "settings_data": {"compact_mode": i % 3 == 0},
            "analytics_data": {"lifetime_events": i % 12, "engagement_score": 30 + (i * 13) % 70},
            "date_joined": joined,
        })
        user.set_password(ctx.demo_password)
        user.save(update_fields=["password"])
        backdate(user, created_at=joined, updated_at=min(ctx.as_of, joined + timedelta(days=30 + i % 100)))
        user.roles.set([roles["participant"]] + ([roles["organizer"]] if is_organizer else []) + ([roles["scanner"]] if is_scanner else []) + ([roles["platform_ops"]] if is_staff else []))
        user.permission_groups.set([groups["participants"]] + ([groups["organizers"]] if is_organizer else []) + ([groups["access-team"]] if is_scanner else []) + ([groups["platform-operations"]] if is_staff else []))

        profile, _ = UserProfile.objects.update_or_create(user=user, defaults={
            "company_name": f"{last} Solutions" if is_organizer else "",
            "organization_name": "",
            "profession": choose(["Entrepreneur", "Étudiant", "Ingénieur", "Créateur", "Comptable", "Consultant", "Designer"], i),
            "country": country,
            "city": city,
            "address": f"Avenue {choose(['Kasa-Vubu', 'Lumumba', 'Mama Yemo', 'Mwepu', 'Likasi'], i)}, {20+i}",
            "latitude": lat + ((i % 7) / 1000),
            "longitude": lon + ((i % 5) / 1000),
            "theme": "dark" if i % 3 else "light",
            "profile_completed": i % 10 != 9,
            "public_profile": is_organizer or i % 6 == 0,
            "searchable": True,
        })
        backdate(profile, created_at=joined, updated_at=min(ctx.as_of, joined + timedelta(days=18)))

        pref, _ = NotificationPreference.objects.update_or_create(user=user, defaults={
            "email_notifications": i % 7 != 0,
            "sms_notifications": i % 4 == 0,
            "push_notifications": True,
            "marketing_notifications": i % 3 == 0,
            "security_notifications": True,
            "event_notifications": True,
            "quiet_hours_enabled": i % 5 == 0,
            "quiet_hours_start": time(22, 0) if i % 5 == 0 else None,
            "quiet_hours_end": time(6, 30) if i % 5 == 0 else None,
        })
        backdate(pref, created_at=joined, updated_at=min(ctx.as_of, joined + timedelta(days=2)))

        for d in range(1 if i >= 30 else 2):
            device = upsert(UserDevice, f"user-{i}-device-{d}", defaults={
                "user": user,
                "device_name": choose(["Samsung Galaxy A54", "iPhone 13", "Tecno Camon 20", "Chrome Windows", "Infinix Note 30"], i + d),
                "device_type": "mobile" if (i + d) % 4 else "desktop",
                "browser": choose(["Chrome", "Safari", "Edge"], i + d),
                "os": choose(["Android 14", "iOS 18", "Windows 11"], i + d),
                "ip_address": f"10.70.{i % 20}.{20+d}",
                "trusted": d == 0,
                "last_used": ctx.as_of - timedelta(days=(i+d) % 40),
                "metadata": {"seed": "makolo-demo", "push_capable": (i + d) % 3 != 0},
            })
            backdate(device, created_at=joined + timedelta(days=3+d), updated_at=ctx.as_of - timedelta(days=(i+d) % 20))

        session = upsert(UserSession, f"user-{i}-session", defaults={
            "user": user,
            "session_key": f"demo-{stable_token(f'session-{i}', 32)}",
            "ip_address": f"10.80.{i % 15}.{30+i%100}",
            "user_agent": choose([
                "Mozilla/5.0 (Linux; Android 14) Chrome/126",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Safari/605",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126",
            ], i),
            "ended_at": None if i % 8 == 0 else ctx.as_of - timedelta(days=i % 20),
            "active": i % 8 == 0,
            "metadata": {"seed": "makolo-demo"},
        })
        session_started = max(joined, ctx.as_of - timedelta(days=40 + i % 150))
        backdate(
            session,
            created_at=session_started,
            started_at=session_started,
            updated_at=ctx.as_of - timedelta(days=i % 20),
        )

        for a, action in enumerate(["Connexion", "Consultation découverte", "Mise à jour profil"]):
            activity = upsert(UserActivity, f"user-{i}-activity-{a}", defaults={
                "user": user,
                "action": action,
                "category": choose(["security", "discovery", "profile"], a),
                "ip_address": f"10.90.{i % 12}.{40+a}",
                "user_agent": "Makolo Web Demo",
                "metadata": {"seed": "makolo-demo", "source": "web"},
            })
            happened = max(joined, ctx.as_of - timedelta(days=(i * 9 + a * 17) % 600))
            backdate(activity, created_at=happened, updated_at=happened)

        if i < 18:
            document = upsert(VerificationDocument, f"user-{i}-verification", defaults={
                "user": user,
                "document_type": choose(["id_card", "passport", "business_license"], i),
                "file": f"accounts/users/demo/verification/demo-{i+1:03d}.pdf",
                "status": choose(["approved", "approved", "pending", "rejected"], i),
                "reviewed_by": ctx.users[0] if ctx.users else (user if is_staff else None),
                "reviewed_at": ctx.as_of - timedelta(days=60+i) if i % 4 != 2 else None,
                "notes": "Document de démonstration — aucune pièce réelle.",
                "metadata": {"seed": "makolo-demo"},
            })
            backdate(document, created_at=joined + timedelta(days=8), updated_at=ctx.as_of - timedelta(days=30+i))

        ctx.users.append(user)

    ctx.staff_users = ctx.users[:3]

    org_specs = [
        ("makolo-live", "Makolo Live", "Lubumbashi", "Production de concerts, festivals et expériences culturelles.", "verified"),
        ("katanga-business-club", "Katanga Business Club", "Lubumbashi", "Rencontres business, networking et conférences.", "verified"),
        ("kin-tech-community", "Kin Tech Community", "Kinshasa", "Communauté tech et innovation congolaise.", "verified"),
        ("copperbelt-sports", "Copperbelt Sports", "Kolwezi", "Événements sportifs et communautaires.", "pending"),
        ("goma-creative-lab", "Goma Creative Lab", "Goma", "Création, design et industries culturelles.", "verified"),
        ("jeunesse-impact-rdc", "Jeunesse Impact RDC", "Kinshasa", "Initiatives jeunesse, leadership et formation.", "new"),
        ("lushi-food-culture", "Lushi Food & Culture", "Lubumbashi", "Gastronomie, patrimoine et rencontres.", "verified"),
        ("horizon-events", "Horizon Events", "Likasi", "Événements corporate et privés.", "suspended"),
    ]
    ctx.organizations.clear()
    for i, (slug, name, city, description, status) in enumerate(org_specs):
        owner = ctx.users[i]
        created = dt(2024, 1 + (i % 8), 5 + i, 10)
        org = upsert(Organization, slug, defaults={
            "name": name,
            "slug": slug,
            "description": description,
            "website": f"https://{slug}.example.com",
            "contact_email": f"contact@{slug}.makolo.test",
            "contact_phone": f"+243 99 55{i:02d} 20{i:02d}",
            "country": "CD",
            "city": city,
            "public_profile": True,
            "verification_status": status,
            "created_by": owner,
        })
        backdate(org, created_at=created, updated_at=min(ctx.as_of, created + timedelta(days=140+i*3)))
        ctx.organizations.append(org)

        member_users = [owner]
        candidate_index = i * 7 + 8
        while len(member_users) < 6:
            candidate = ctx.users[candidate_index % len(ctx.users)]
            candidate_index += 1
            if candidate.id not in {member.id for member in member_users}:
                member_users.append(candidate)
        member_roles = [
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
            OrganizationRole.EVENT_MANAGER,
            OrganizationRole.FINANCE,
            OrganizationRole.MARKETING,
            OrganizationRole.SCANNER_MANAGER,
        ]
        for j, (member, role) in enumerate(zip(member_users, member_roles)):
            membership = upsert(OrganizationMembership, f"{slug}-{role}", defaults={
                "organization": org,
                "user": member,
                "role": role,
                "is_active": not (i == 7 and j > 2),
                "invited_by": owner if j else None,
            })
            backdate(membership, joined_at=created + timedelta(days=3+j*5), updated_at=min(ctx.as_of, created + timedelta(days=90+j)))
            if role != OrganizationRole.OWNER:
                member.is_organizer = True
                member.save(update_fields=["is_organizer"])

    for i, user in enumerate(ctx.users):
        for offset in range(2 if i % 4 else 3):
            org = ctx.organizations[(i + offset * 3) % len(ctx.organizations)]
            if org.verification_status == OrganizationVerificationStatus.SUSPENDED and i % 3:
                continue
            follow = upsert(OrganizationFollow, f"user-{i}-org-{org.slug}", defaults={
                "organization": org,
                "user": user,
                "notify_new_events": True,
                "notify_announcements": i % 5 != 0,
                "email_new_events": i % 3 == 0,
                "email_announcements": i % 6 == 0,
            })
            when = max(dt(2024, 2, 1), ctx.as_of - timedelta(days=(i * 13 + offset * 31) % 860))
            backdate(follow, followed_at=when, updated_at=min(ctx.as_of, when + timedelta(days=45)))

    ctx.add("users", len(ctx.users))
    ctx.add("organizations", len(ctx.organizations))
