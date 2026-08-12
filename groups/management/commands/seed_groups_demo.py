from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from organizations.models import Organization

from groups.models import Group, GroupVisibility
from groups.services import create_group


User = get_user_model()


class Command(BaseCommand):
    help = "Ajoute quelques Groupes de démonstration sans reseed du reste de Makolo."

    def handle(self, *args, **options):
        personal_owner = User.objects.filter(is_active=True).order_by("date_joined", "pk").first()
        if personal_owner:
            self._personal_group(personal_owner, "Promotion Informatique 2026")

        for space in Organization.objects.order_by("created_at", "pk")[:2]:
            owner_mandate = (
                Mandate.objects.filter(
                    space=space,
                    scope_type=AuthorityScope.SPACE,
                    status=MandateStatus.ACTIVE,
                    revoked_at__isnull=True,
                    role__code=SystemRoleCode.SPACE_OWNER,
                    role__is_active=True,
                )
                .select_related("profile")
                .order_by("granted_at", "pk")
                .first()
            )
            if not owner_mandate:
                continue
            self._space_group(owner_mandate.profile, space, "VIP")
            self._space_group(
                owner_mandate.profile,
                space,
                f"Employés {space.name}"[:180],
            )

        self.stdout.write(self.style.SUCCESS("Groupes de démonstration prêts."))

    def _personal_group(self, actor, name):
        if Group.objects.filter(owner_profile=actor, space__isnull=True, name=name).exists():
            return
        create_group(
            actor=actor,
            name=name,
            description="Groupe de démonstration Makolo pour une population personnelle.",
        )

    def _space_group(self, actor, space, name):
        if Group.objects.filter(space=space, owner_profile__isnull=True, name=name).exists():
            return
        create_group(
            actor=actor,
            space=space,
            name=name,
            description="Groupe de démonstration rattaché à cet Espace.",
            visibility=GroupVisibility.SPACE,
        )
