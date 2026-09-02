from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from activities.models import Activity, ActivityStatus, ActivityVisibility
from groups.models import Group, GroupMembership, GroupMembershipStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from trust.models import Report

from .models import ContributionKind
from .services import create_contribution


User = get_user_model()


class M5ReportingBridgeTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="m5-report-member", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="m5-report-outsider", password="StrongPass2026!")
        self.owner = User.objects.create_user(username="m5-report-owner", password="StrongPass2026!")
        self.space = Organization.objects.create(name="M5 Reporting Space", created_by=self.owner, public_profile=True)
        self.group = Group.objects.create(name="M5 Reporting Group", owner_profile=self.owner, created_by=self.owner)
        GroupMembership.objects.create(group=self.group, profile=self.member, status=GroupMembershipStatus.ACTIVE)
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="M5 Reporting Activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.contribution = create_contribution(
            actor=self.member,
            kind=ContributionKind.DISCUSSION,
            body="Contexte vérifiable",
            group=self.group,
            activity=self.activity,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.member,
            beneficiary=self.member,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
        )
        self.client = APIClient()

    def test_visible_contribution_report_creates_canonical_m4_report(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            f"/api/v1/social/contributions/{self.contribution.pk}/report/",
            {"description": "Comportement à examiner"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        report = Report.objects.get(reporter=self.member)
        self.assertEqual(report.activity_id, self.activity.pk)
        from social import models as social_models
        self.assertFalse(hasattr(social_models, "SocialReport"))

    def test_outsider_cannot_report_private_group_contribution(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.post(
            f"/api/v1/social/contributions/{self.contribution.pk}/report/",
            {"description": "Invisible pour moi"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Report.objects.filter(reporter=self.outsider).exists())
