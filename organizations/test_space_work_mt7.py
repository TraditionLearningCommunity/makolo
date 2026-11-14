"""MT7: cross-archetype Work navigation, bounded pages and authority."""
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization, SpaceArchetype
from organizations.space_work_navigation import (
    work_back_url, work_page_number,
)
from organizations.space_work_web import _compose_sections


class SpaceMetierMT7Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mt7-owner", password="x")
        self.operator = User.objects.create_user(username="mt7-limited", password="x")
        self.stranger = User.objects.create_user(username="mt7-stranger", password="x")
        self.space = Organization.objects.create(
            name="Métier MT7", slug="metier-mt7",
            created_by=self.owner, archetype=SpaceArchetype.GENERIC,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.work_url = reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        )
        self.collection_url = reverse(
            "organizations:space-work-collection",
            kwargs={"slug": self.space.slug, "section": "activities"},
        )

    def activity(self, title):
        return Activity.objects.create(
            space=self.space, created_by=self.owner,
            title=title, status=ActivityStatus.PUBLISHED,
        )

    def test_collection_from_n1_to_n2_retains_page_and_section(self):
        created = [self.activity(f"Activité {index:02d}") for index in range(14)]
        root = self.client.get(self.work_url)
        self.assertEqual(root.status_code, 200)
        activities = next(
            section for section in root.context["work_sections"]
            if section["key"] == "activities"
        )
        self.assertEqual(len(activities["items"]), 12)
        self.assertTrue(activities["has_more"])
        self.assertIn("/work/collection/activities/", activities["continuation_url"])
        self.assertIn("page=2", activities["continuation_url"])
        second = self.client.get(activities["continuation_url"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.context["work_collection_page"], 2)
        self.assertEqual(second.context["projection"]["coverage_state"], "partial")
        section = second.context["work_sections"][0]
        self.assertEqual(len(section["items"]), 2)
        self.assertEqual(
            {item["source"]["id"] for item in section["items"]},
            {str(created[-2].pk), str(created[-1].pk)},
        )
        n2_url = section["items"][0]["owner_url"]
        self.assertIn("work_origin_page=2", n2_url)
        n2 = self.client.get(n2_url)
        self.assertEqual(n2.status_code, 200)
        back = n2.context["work_depth"]["back_url"]
        self.assertEqual(urlsplit(back).path, self.collection_url)
        self.assertEqual(parse_qs(urlsplit(back).query)["page"], ["2"])
        self.assertEqual(parse_qs(urlsplit(back).query)["responsibility"], ["all"])

    def test_nested_n2_occurrence_retains_origin_without_reusing_owner_page(self):
        for i in range(12):
            self.activity(f"Activité {i:02d}")
        work = self.activity("Activité 12")
        date = Occurrence.objects.create(
            activity=work, label="Date de terrain",
            start_at=timezone.now() + timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        page = self.client.get(self.collection_url + "?page=2")
        n2_url = page.context["work_sections"][0]["items"][0]["owner_url"]
        self.assertIn("work_origin_page=2", n2_url)
        n2 = self.client.get(n2_url)
        self.assertEqual(n2.status_code, 200)
        child = next(
            row for row in n2.context["work_depth"]["related"]
            if row["identity"] == f"occurrence:{date.pk}"
        )
        self.assertIn("work_origin_page=2", child["url"])
        detail = self.client.get(child["url"])
        self.assertEqual(detail.status_code, 200)
        self.assertIn(
            "work_origin_page=2", detail.context["work_depth"]["back_url"],
        )

    def test_collection_pages_are_bounded_and_not_an_authority_source(self):
        self.activity("Activité établie")
        for page in ("0", "-1", "835", "99999", "abc", "1.2"):
            self.assertEqual(
                self.client.get(self.collection_url, {"page": page}).status_code,
                404, page,
            )
        forbidden = reverse(
            "organizations:space-work-collection",
            kwargs={"slug": self.space.slug, "section": "internal-private"},
        )
        self.assertEqual(self.client.get(forbidden).status_code, 404)
        self.assertEqual(
            self.client.get(
                self.collection_url, {"work_origin_page": "1"}
            ).status_code, 200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "organizations:space-work-depth",
                    kwargs={"slug": self.space.slug, "kind": "activity",
                            "owner_id": Activity.objects.first().pk},
                ), {"work_origin_page": "invalid"}
            ).status_code, 404,
        )
        self.client.force_login(self.stranger)
        self.assertNotEqual(self.client.get(self.collection_url).status_code, 200)

    def test_limited_mandate_never_expands_collection_or_depth(self):
        allowed = self.activity("Autorisée par mandat")
        hidden = self.activity("Invisible hors mandat")
        mandate = grant_activity_role(
            profile=self.operator, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(self.operator)
        result = self.client.get(self.collection_url)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Autorisée par mandat")
        self.assertNotContains(result, "Invisible hors mandat")
        hidden_url = reverse(
            "organizations:space-work-depth",
            kwargs={"slug": self.space.slug, "kind": "activity",
                    "owner_id": hidden.pk},
        )
        self.assertEqual(self.client.get(hidden_url).status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertNotEqual(self.client.get(self.collection_url).status_code, 200)

    def test_only_real_web_handoff_is_exposed_as_secondary_action(self):
        journey_id = "11111111-1111-4111-8111-111111111111"
        item = {
            "key": f"journey:{journey_id}",
            "source": {"kind": "journey", "id": journey_id},
            "kind": "service_case",
            "title": "Dossier",
            "summary": None,
            "context": {"activity": {"id": journey_id}},
            "links": {"detail": "/services/operator/cases/1/"},
            "capabilities": ["view", "open_service_case"],
            "owner_handoffs": [
                {"intent": "inspect", "channel": "space_work",
                 "label": "Consulter", "url": "/api/work/",
                 "owner": {"kind": "journey", "id": journey_id}},
                {"intent": "open_service_case", "channel": "web",
                 "label": "Travailler sur le dossier",
                 "url": "/services/operator/cases/1/",
                 "owner": {"kind": "journey", "id": journey_id}},
                {"intent": "open_service_case", "channel": "web",
                 "label": "Interdit", "url": "/services/operator/cases/999/",
                 "owner": {"kind": "journey", "id": "999"}},
                {"intent": "open_day_of", "channel": "api",
                 "label": "Faux Jour J", "url": "/api/v1/test/",
                 "owner": {"kind": "journey", "id": journey_id}},
            ],
        }
        sections = {"requests": {
            "representation": "Demandes", "role": "continuity",
            "items": [item], "has_more": False,
        }}
        composed = _compose_sections(
            self.space, {
                "sections": sections,
                "presentation": {"section_order": ["requests"]},
                "responsibility": "all",
            },
        )
        self.assertEqual(len(composed), 1)
        self.assertEqual(composed[0]["items"][0]["web_handoffs"], [
            {"label": "Travailler sur le dossier",
             "url": "/services/operator/cases/1/"},
        ])

    def test_all_eight_archetypes_preserve_owner_identity_and_reading_groups(self):
        cases = [
            SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
            SpaceArchetype.EDUCATION, SpaceArchetype.SERVICE_PROVIDER,
            SpaceArchetype.COMMERCE, SpaceArchetype.TRANSPORT_OPERATOR,
            SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA,
        ]
        for archetype in cases:
            with self.subTest(archetype=archetype):
                self.space.archetype = archetype
                self.space.save(update_fields=["archetype", "updated_at"])
                work = self.activity(f"Vérité {archetype}")
                response = self.api.get(reverse(
                    "organizations_api:workspace-work",
                    kwargs={"slug": self.space.slug},
                ))
                self.assertEqual(response.status_code, 200, response.data)
                groups = response.data["business_world"]["reading_groups"]
                self.assertTrue(groups)
                keys = [
                    key for group in groups for key in group["section_keys"]
                ]
                self.assertIn("activities", keys)
                self.assertEqual(
                    response.data["presentation"]["section_order"], keys,
                )
                row = next(
                    item for section in response.data["sections"].values()
                    for item in section["items"]
                    if item["source"] == {
                        "kind": "activity", "id": str(work.pk),
                    }
                )
                self.assertEqual(
                    row["owner_reference"], {"kind": "activity", "id": str(work.pk)},
                )

    def test_mt8_root_preview_with_continuation_is_not_complete(self):
        for index in range(14):
            self.activity(f"Programme réel {index:02d}")
        response = self.api.get(reverse(
            "organizations_api:workspace-work",
            kwargs={"slug": self.space.slug},
        ))
        self.assertEqual(response.status_code, 200)
        activities = response.data["sections"]["activities"]
        self.assertEqual(len(activities["items"]), 12)
        self.assertTrue(activities["has_more"])
        self.assertEqual(activities["coverage_state"], "partial")
        self.assertEqual(response.data["coverage_state"], "partial")
        self.assertEqual(response.data["composition_state"], "partial")

    def test_navigation_helper_preserves_scope_but_never_creates_authority(self):
        self.assertIsNone(work_page_number(None))
        self.assertEqual(work_page_number(None, required=True), 1)
        root = work_back_url(
            space=self.space, responsibility="mandate:example",
            section="activities",
        )
        self.assertTrue(root.endswith("#work-activities"))
        self.assertEqual(
            parse_qs(urlsplit(root).query)["responsibility"],
            ["mandate:example"],
        )
