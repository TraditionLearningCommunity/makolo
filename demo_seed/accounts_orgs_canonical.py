from __future__ import annotations

from datetime import time, timedelta

from accounts.models import NotificationPreference, User, UserProfile
from organizations.models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    OrganizationRole,
    OrganizationVerificationStatus,
)

from .common import SeedContext, backdate, choose, dt, upsert


FIRST_NAMES = ["Amina", "Grâce", "Sarah", "Naomi", "Junior", "Patrick", "David", "Esther"]
LAST_NAMES = ["Kabongo", "Ilunga", "Mutombo", "Kasongo", "Mbuyi", "Kalala", "Mukendi", "Tshibangu"]
CITIES = [
    ("Lubumbashi", "CD"),
    ("Kinshasa", "CD"),
    ("Kolwezi", "CD"),
    ("Likasi", "CD"),
    ("Goma", "CD"),
]


ORG_SPECS = [
    ("makolo-live", "Makolo Live", "Lubumbashi", "verified"),
    ("katanga-business-club", "Katanga Business Club", "Lubumbashi", "verified"),
    ("kin-tech-community", "Kin Tech Community", "Kinshasa", "verified"),
    ("copperbelt-sports", "Copperbelt Sports", "Kolwezi", "pending"),
    ("goma-creative-lab", "Goma Creative Lab", "Goma", "verified"),
    ("jeunesse-impact-rdc", "Jeunesse Impact RDC", "Kinshasa", "new"),
    ("lushi-food-culture", "Lushi Food & Culture", "Lubumbashi", "verified"),
    ("horizon-events", "Horizon Events", "Likasi", "suspended"),
]


def seed_accounts_and_organizations(ctx: SeedContext) -> None:
    """Seed Profiles and Spaces without retired account-level business authority."""
    ctx.users.clear()
    base_date = dt(2024, 1, 8, 8)
    for i in range(ctx.cfg["users"]):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
        city, country = CITIES[i % len(CITIES)]
        joined = base_date + timedelta(days=(i * 11) % 910, hours=i % 9)
        user = upsert(User, f"user-{i+1:03d}", defaults={
            "email": f"demo.user{i+1:03d}@makolo.test",
            "username": f"demo{i+1:03d}",
            "first_name": first,
            "last_name": last,
            "phone": f"+243 97 {1000000+i:07d}",
            "bio": f"{first} {last}, Profil de démonstration Makolo à {city}.",
            "language": "fr",
            "timezone": "Africa/Lubumbashi" if city != "Kinshasa" else "Africa/Kinshasa",
            "is_active": True,
            "is_staff": i < 3,
            "is_superuser": i == 0,
            "email_verified": i % 8 != 7,
            "phone_verified": i % 4 == 0,
            "onboarding_completed": i % 9 != 8,
            "onboarding_step": 5 if i % 9 != 8 else i % 5,
            "last_seen": ctx.as_of - timedelta(hours=(i * 3) % 300),
            "require_2fa": i < 3 or i % 17 == 0,
            "metadata": {"seed": "makolo-demo", "city": city},
            "preferences": {"topics": choose([["music", "culture"], ["business", "tech"], ["community", "sports"]], i)},
            "date_joined": joined,
        })
        user.set_password(ctx.demo_password)
        user.save(update_fields=["password"])
        backdate(user, created_at=joined, updated_at=min(ctx.as_of, joined + timedelta(days=30)))
        profile, _ = UserProfile.objects.update_or_create(user=user, defaults={
            "profession": choose(["Entrepreneur", "Étudiant", "Ingénieur", "Créateur", "Comptable"], i),
            "country": country,
            "city": city,
            "theme": "dark" if i % 3 else "light",
            "public_profile": i < 16 or i % 6 == 0,
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
            "service_notifications": True,
            "opportunity_notifications": True,
            "quiet_hours_enabled": i % 5 == 0,
            "quiet_hours_start": time(22, 0) if i % 5 == 0 else None,
            "quiet_hours_end": time(6, 30) if i % 5 == 0 else None,
        })
        backdate(pref, created_at=joined, updated_at=min(ctx.as_of, joined + timedelta(days=2)))
        ctx.users.append(user)

    ctx.staff_users = ctx.users[:3]
    ctx.organizations.clear()
    roles = [
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
        OrganizationRole.EVENT_MANAGER,
        OrganizationRole.FINANCE,
        OrganizationRole.MARKETING,
        OrganizationRole.SCANNER_MANAGER,
    ]
    for i, (slug, name, city, verification_status) in enumerate(ORG_SPECS):
        owner = ctx.users[i]
        created = dt(2024, 1 + (i % 8), 5 + i, 10)
        org = upsert(Organization, slug, defaults={
            "name": name,
            "slug": slug,
            "description": f"Espace de démonstration Makolo — {name}.",
            "contact_email": f"contact@{slug}.makolo.test",
            "country": "CD",
            "city": city,
            "public_profile": True,
            "verification_status": verification_status,
            "created_by": owner,
        })
        backdate(org, created_at=created, updated_at=min(ctx.as_of, created + timedelta(days=140)))
        ctx.organizations.append(org)
        members = [ctx.users[(i + j * 7) % len(ctx.users)] for j in range(len(roles))]
        members[0] = owner
        for j, (member, role) in enumerate(zip(members, roles)):
            membership = upsert(OrganizationMembership, f"{slug}-{role}", defaults={
                "organization": org,
                "user": member,
                "role": role,
                "is_active": not (i == 7 and j > 2),
                "invited_by": owner if j else None,
            })
            backdate(membership, joined_at=created + timedelta(days=3+j*5), updated_at=created + timedelta(days=90+j))

    for i, user in enumerate(ctx.users):
        org = ctx.organizations[i % len(ctx.organizations)]
        if org.verification_status != OrganizationVerificationStatus.SUSPENDED:
            follow = upsert(OrganizationFollow, f"user-{i}-org-{org.slug}", defaults={
                "organization": org,
                "user": user,
                "notify_new_events": True,
                "notify_announcements": True,
                "email_new_events": i % 3 == 0,
                "email_announcements": i % 6 == 0,
            })
            backdate(follow, followed_at=max(dt(2024, 2, 1), ctx.as_of - timedelta(days=(i * 13) % 860)))

    ctx.add("users", len(ctx.users))
    ctx.add("organizations", len(ctx.organizations))
