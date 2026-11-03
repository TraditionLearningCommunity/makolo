"""MT6: real Creative/Media N2 and N3 owner boundaries."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import (
    grant_activity_role, grant_space_role, revoke_mandate,
)
from organizations.models import Organization, SpaceArchetype


class MT6CreativeMediaDepthTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mt6-owner", password="x",
        )
        self.operator = User.objects.create_user(
            username="mt6-operator", password="x",
        )
        self.outsider = User.objects.create_user(
            username="mt6-outsider", password="x",
        )
        self.space = Organization.objects.create(
            name="Studio MT6", slug="studio-mt6",
            created_by=self.owner, archetype=SpaceArchetype.CREATIVE,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.work_url = reverse(
            "organizations_api:workspace-work",
            kwargs={"slug": self.space.slug},
        )

    def activity(self, title="Œuvre durable", status=ActivityStatus.PUBLISHED):
        return Activity.objects.create(
            space=self.space, created_by=self.owner,
            title=title, short_description="Création réelle",
            description="Notes de création", status=status,
        )

    def depth(self, kind, identity, **params):
        from urllib.parse import urlencode
        path = reverse(
            "organizations:space-work-depth-g4",
            kwargs={"slug": self.space.slug, "kind": kind,
                    "owner_id": identity},
        )
        return path + ("?" + urlencode(params) if params else "")

    def test_creative_n1_n2_related_and_owner_handoffs(self):
        work = self.activity()
        occurrence = Occurrence.objects.create(
            activity=work, label="Présentation publique",
            start_at=timezone.now() + timedelta(days=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        root = self.client.get(reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        ))
        self.assertEqual(root.status_code, 200)
        entry = next(
            item for section in root.context["work_sections"]
            for item in section["items"]
            if item["source"] == {"kind": "activity", "id": str(work.pk)}
        )
        self.assertIn("/work/g4/activity/", entry["owner_url"])
        detail = self.client.get(entry["owner_url"])
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Notes de création")
        self.assertContains(detail, "Présentations et réalisations")
        self.assertContains(detail, "Présentation publique")
        self.assertContains(detail, "Gérer les ressources")
        self.assertNotContains(detail, "Acheter")
        item = detail.context["work_g4"]["related"][0]
        self.assertEqual(item["source"]["id"], str(occurrence.pk))
        self.assertTrue(item["url"])
        child = self.client.get(item["url"])
        self.assertEqual(child.status_code, 200)
        self.assertEqual(child.context["work_g4"]["kind"], "occurrence")
        self.assertIn("/work/g4/activity/", child.context["work_g4"]["back_url"])

    def test_media_production_is_not_an_edition_and_has_no_fake_feed(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        production = self.activity("Journal du soir")
        edition = Occurrence.objects.create(
            activity=production, label="Édition du soir",
            start_at=timezone.now() + timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        response = self.api.get(self.work_url, {
            "kind": "activity", "id": str(production.pk),
        })
        self.assertEqual(response.status_code, 200, response.data)
        item = response.data["selection"]
        self.assertEqual(item["g4_detail"]["language"], "Production")
        self.assertEqual(item["related_occurrences"]["items"][0]["source"]["id"],
                         str(edition.pk))
        self.assertEqual(
            item["context"]["next_occurrence"]["id"], str(edition.pk),
        )
        self.assertNotIn("feed", str(item).lower())
        self.assertNotIn("portfolio", str(item).lower())
        detail = self.client.get(self.depth("activity", production.pk))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Éditions et réalisations")
        self.assertContains(detail, "Édition du soir")

    def test_related_is_bounded_and_stale_scheduled_not_openable(self):
        work = self.activity()
        expired = Occurrence.objects.create(
            activity=work, label="Ancienne date encore planifiée",
            start_at=timezone.now() - timedelta(days=8),
            end_at=timezone.now() - timedelta(days=7),
            status=OccurrenceStatus.SCHEDULED,
        )
        for i in range(13):
            Occurrence.objects.create(
                activity=work, label=f"Date {i}",
                start_at=timezone.now() + timedelta(days=i + 1),
                status=OccurrenceStatus.SCHEDULED,
            )
        response = self.api.get(self.work_url, {
            "kind": "activity", "id": str(work.pk),
        })
        self.assertEqual(response.status_code, 200)
        dates = response.data["selection"]["related_occurrences"]
        self.assertEqual(len(dates["items"]), 12)
        self.assertTrue(dates["has_more"])
        first = next(x for x in dates["items"]
                     if x["source"]["id"] == str(expired.pk))
        self.assertFalse(first["openable"])
        second = self.api.get(self.work_url, {
            "kind": "activity", "id": str(work.pk), "related_offset": 12,
        })
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["selection"]["related_occurrences"]["offset"], 12)
        self.assertEqual(len(second.data["selection"]["related_occurrences"]["items"]), 2)
        detail = self.client.get(self.depth("activity", work.pk, page="2"))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.context["work_g4"]["related"]), 2)

    def test_mandate_limits_details_and_revocation_removes_access(self):
        allowed = self.activity("Œuvre autorisée")
        other = self.activity("Œuvre interdite")
        mandate = grant_activity_role(
            profile=self.operator, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.depth("activity", allowed.pk)).status_code, 200)
        self.assertEqual(self.client.get(self.depth("activity", other.pk)).status_code, 404)
        self.api.force_authenticate(self.operator)
        denied = self.api.get(self.work_url, {
            "kind": "activity", "id": str(other.pk),
        })
        self.assertEqual(denied.status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(self.depth("activity", allowed.pk)).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertNotEqual(
            self.client.get(self.depth("activity", allowed.pk)).status_code, 200,
        )

    def test_native_creation_uses_activity_owner_and_rejects_forgery(self):
        create = reverse(
            "organizations_api:workspace-work-activity-create",
            kwargs={"slug": self.space.slug},
        )
        data = {
            "title": "Nouveau spectacle", "short_description": "Brouillon",
            "description": "", "visibility": "private",
        }
        response = self.api.post(create, data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        work = Activity.objects.get(pk=response.data["activity"]["id"])
        self.assertEqual(work.space_id, self.space.pk)
        self.assertEqual(work.status, ActivityStatus.DRAFT)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.api.post(
            create, {**data, "organization": str(self.space.pk)},
            format="json",
        ).status_code, 400)
        self.api.force_authenticate(self.outsider)
        self.assertEqual(self.api.post(create, data, format="json").status_code, 404)
