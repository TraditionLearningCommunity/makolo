from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.template import Context, Template
from django.test import TestCase
from django.utils import timezone

from access.models import Access
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from authorization.models import Mandate
from authorization.services import grant_space_role
from authorization.constants import SystemRoleCode
from crm.models import CRMContact
from groups.models import Group, GroupMembership, GroupMembershipStatus
from organizations.models import Organization, OrganizationFollow

from .models import Contribution, ContributionKind, ContributionStatus, ContributionVisibility
from .selectors import group_contributions
from .services import create_contribution, moderate_contribution, share_activity_to_group


User = get_user_model()


class M5ContributionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="m5-owner", email="m5-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="m5-member", email="m5-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="m5-outsider", email="m5-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="M5 Action Space", created_by=self.owner, public_profile=True)
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner, source="m5-test")
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="M5 Useful Activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.group = Group.objects.create(name="M5 Private Action Group", owner_profile=self.owner, created_by=self.owner)
        GroupMembership.objects.create(group=self.group, profile=self.member, status=GroupMembershipStatus.ACTIVE)

    def test_follow_is_private_relation_without_mandate_or_crm_contact(self):
        OrganizationFollow.objects.create(organization=self.space, user=self.member)
        self.assertEqual(Mandate.objects.filter(profile=self.member, space=self.space).count(), 0)
        self.assertFalse(CRMContact.objects.filter(organization=self.space, user=self.member).exists())
        OrganizationFollow.objects.filter(organization=self.space, user=self.member).delete()
        self.assertFalse(OrganizationFollow.objects.filter(organization=self.space, user=self.member).exists())

    def test_root_contribution_without_context_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Orpheline")
        self.assertEqual(Contribution.objects.count(), 0)

    def test_official_update_requires_real_authority(self):
        update = create_contribution(
            actor=self.owner,
            kind=ContributionKind.UPDATE,
            body="Horaire confirmé par l'équipe.",
            activity=self.activity,
            visibility=ContributionVisibility.PUBLIC,
        )
        self.assertEqual(update.space, self.space)
        self.assertEqual(update.visibility, ContributionVisibility.PUBLIC)
        with self.assertRaises(PermissionDenied):
            create_contribution(
                actor=self.member,
                kind=ContributionKind.UPDATE,
                body="Je prétends être officiel.",
                activity=self.activity,
            )

    def test_group_member_can_contribute_outsider_cannot_and_content_stays_private(self):
        contribution = create_contribution(
            actor=self.member,
            kind=ContributionKind.DISCUSSION,
            body="Qui prend le matériel ?",
            group=self.group,
        )
        self.assertEqual(contribution.visibility, ContributionVisibility.CONTEXT)
        self.assertEqual(list(group_contributions(viewer=self.member, group=self.group)), [contribution])
        with self.assertRaises(PermissionDenied):
            create_contribution(actor=self.outsider, kind=ContributionKind.DISCUSSION, body="Intrusion", group=self.group)
        with self.assertRaises(PermissionDenied):
            list(group_contributions(viewer=self.outsider, group=self.group))

    def test_field_note_requires_real_occurrence_relation(self):
        with self.assertRaises(PermissionDenied):
            create_contribution(
                actor=self.outsider,
                kind=ContributionKind.FIELD_NOTE,
                body="Information non vérifiable.",
                occurrence=self.occurrence,
            )
        GroupMembership.objects.create(group=self.group, profile=self.outsider, status=GroupMembershipStatus.ACTIVE)
        note = create_contribution(
            actor=self.outsider,
            kind=ContributionKind.FIELD_NOTE,
            body="Entrée opérationnelle côté nord.",
            group=self.group,
            occurrence=self.occurrence,
        )
        self.assertEqual(note.activity, self.activity)
        self.assertEqual(note.occurrence, self.occurrence)

    def test_reply_inherits_context_and_depth_is_bounded(self):
        root = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Point de départ", group=self.group)
        reply = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Réponse", parent=root)
        self.assertEqual(reply.group, root.group)
        self.assertEqual(reply.visibility, root.visibility)
        with self.assertRaises(ValidationError):
            create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Trop profond", parent=reply)

    def test_internal_share_references_activity_and_grants_no_access(self):
        before = Access.objects.filter(beneficiary=self.member, activity=self.activity).count()
        share = share_activity_to_group(actor=self.member, group=self.group, activity=self.activity, body="À faire ensemble")
        self.assertEqual(share.kind, ContributionKind.SHARE)
        self.assertEqual(share.activity, self.activity)
        self.assertEqual(Access.objects.filter(beneficiary=self.member, activity=self.activity).count(), before)

    def test_author_can_remove_own_content_but_cannot_remove_another_author(self):
        mine = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Mon message", group=self.group)
        other = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Autre message", group=self.group)
        moderate_contribution(actor=self.member, contribution=mine, status=ContributionStatus.REMOVED)
        mine.refresh_from_db()
        self.assertEqual(mine.status, ContributionStatus.REMOVED)
        with self.assertRaises(PermissionDenied):
            moderate_contribution(actor=self.outsider, contribution=other, status=ContributionStatus.REMOVED)

    def test_user_text_is_plain_escaped_content(self):
        payload = '<script>alert(1)</script><a href="javascript:alert(2)">ouvrir</a>'
        contribution = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body=payload, group=self.group)
        rendered = Template("{{ contribution.body }}").render(Context({"contribution": contribution}))
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('<a href="javascript:', rendered)
        self.assertIn("&lt;script&gt;", rendered)
