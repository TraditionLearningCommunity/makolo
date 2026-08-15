from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from groups.models import Group, GroupMembership, GroupMembershipStatus
from groups.services import create_snapshot
from organizations.models import Organization, OrganizationMembership, OrganizationRole

from .audiences import (
    add_audience_member,
    create_audience_from_group,
    create_audience_from_snapshot,
    create_static_audience,
)
from .canonical_models import AudienceMember, AudienceMemberSource
from .models import CRMContact, MarketingConsent
from .permissions import user_can_view_customer_360_financials


User = get_user_model()


class AudienceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="audience-owner",
            email="owner@audience.test",
            password="Audience-2026!",
        )
        self.marketing = User.objects.create_user(
            username="audience-marketing",
            email="marketing@audience.test",
            password="Audience-2026!",
        )
        self.member = User.objects.create_user(
            username="audience-member",
            email="member@audience.test",
            first_name="Mina",
            password="Audience-2026!",
        )
        self.other_member = User.objects.create_user(
            username="audience-member-2",
            email="member2@audience.test",
            password="Audience-2026!",
        )
        self.space = Organization.objects.create(name="Audience Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Other Audience Space", created_by=self.owner)
        OrganizationMembership.objects.create(
            organization=self.space,
            user=self.owner,
            role=OrganizationRole.OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.space,
            user=self.marketing,
            role=OrganizationRole.MARKETING,
        )
        self.contact = CRMContact.objects.create(
            organization=self.space,
            user=self.member,
            email=self.member.email,
            name="Mina",
            source="manual",
            marketing_consent=MarketingConsent.UNSUBSCRIBED,
        )
        CRMContact.objects.create(
            organization=self.space,
            user=self.other_member,
            email=self.other_member.email,
            source="manual",
        )
        self.group = Group.objects.create(
            name="Cohorte Makolo",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(
            group=self.group,
            profile=self.member,
            status=GroupMembershipStatus.ACTIVE,
        )

    def test_static_audience_member_is_unique_and_does_not_change_consent(self):
        audience = create_static_audience(
            organization=self.space,
            name="Contacts choisis",
            created_by=self.marketing,
            profiles=[self.member],
        )
        add_audience_member(audience=audience, profile=self.member, actor=self.marketing)

        self.assertEqual(AudienceMember.objects.filter(audience=audience, profile=self.member).count(), 1)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.marketing_consent, MarketingConsent.UNSUBSCRIBED)

    def test_group_source_is_snapshotted_at_creation(self):
        audience = create_audience_from_group(
            organization=self.space,
            group=self.group,
            name="Cohorte actuelle",
            created_by=self.marketing,
        )
        GroupMembership.objects.create(
            group=self.group,
            profile=self.other_member,
            status=GroupMembershipStatus.ACTIVE,
        )

        self.assertEqual(audience.members.count(), 1)
        member = audience.members.get()
        self.assertEqual(member.profile_id, self.member.pk)
        self.assertEqual(member.source, AudienceMemberSource.GROUP)

    def test_snapshot_source_copies_exact_frozen_population(self):
        snapshot = create_snapshot(actor=self.owner, group=self.group, name="Cohorte figée")
        GroupMembership.objects.create(
            group=self.group,
            profile=self.other_member,
            status=GroupMembershipStatus.ACTIVE,
        )
        audience = create_audience_from_snapshot(
            organization=self.space,
            snapshot=snapshot,
            name="Snapshot campagne",
            created_by=self.marketing,
        )

        self.assertEqual(set(audience.members.values_list("profile_id", flat=True)), {self.member.pk})
        self.assertEqual(audience.source_snapshot_id, snapshot.pk)

    def test_cross_space_and_personal_groups_are_rejected(self):
        other_group = Group.objects.create(name="Other Group", space=self.other_space, created_by=self.owner)
        personal_group = Group.objects.create(name="Personal Group", owner_profile=self.owner, created_by=self.owner)

        with self.assertRaises(ValidationError):
            create_audience_from_group(
                organization=self.space,
                group=other_group,
                name="Interdit B",
                created_by=self.marketing,
            )
        with self.assertRaises(ValidationError):
            create_audience_from_group(
                organization=self.space,
                group=personal_group,
                name="Interdit personnel",
                created_by=self.marketing,
            )

    def test_marketing_can_manage_audience_without_financial_permission(self):
        self.client.force_login(self.marketing)
        response = self.client.get(reverse("crm:audience-list", kwargs={"slug": self.space.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(user_can_view_customer_360_financials(self.marketing, self.space))

        response_other = self.client.get(reverse("crm:audience-list", kwargs={"slug": self.other_space.slug}))
        self.assertEqual(response_other.status_code, 403)
