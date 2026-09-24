from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification, NotificationCategory, NotificationKind
from notifications.navigation import build_notification_navigation


class M100NotificationNavigationContractTests(SimpleTestCase):
    def _notification(self, **metadata):
        return Notification(
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Navigation",
            message="Navigation structurée",
            metadata=metadata,
        )

    def test_legacy_priority_and_identifiers_remain_compatible(self):
        ids = {key: str(uuid4()) for key in ("event_id", "order_id", "payment_id", "ticket_id")}
        navigation = build_notification_navigation(self._notification(**ids))

        self.assertEqual(navigation["target"], "ticket")
        self.assertEqual(navigation["ticket_id"], ids["ticket_id"])
        self.assertEqual(navigation["payment_id"], ids["payment_id"])
        self.assertEqual(navigation["order_id"], ids["order_id"])
        self.assertEqual(navigation["event_id"], ids["event_id"])
        self.assertEqual(navigation["resource"], {"kind": "ticket", "id": ids["ticket_id"]})
        self.assertEqual(
            navigation["links"]["api"],
            f"/api/v1/tickets/tickets/{ids['ticket_id']}/",
        )

    def test_mature_identifiers_point_to_owner_apis_without_parsing_html(self):
        cases = (
            ("access_id", "access", "access", "/api/v1/me/accesses/{id}/"),
            ("journey_id", "journey", "journey", "/api/v1/me/journeys/{id}/"),
            ("occurrence_id", "occurrence", "occurrence", "/api/v1/occurrences/{id}/"),
            ("conversation_id", "conversation", "conversation", "/api/v1/conversations/{id}/"),
            ("group_id", "group", "group", "/api/v1/me/collectives/groups/{id}/"),
            ("partner_id", "partner", "partner_relationship", "/api/v1/me/partners/{id}/"),
            ("dossier_id", "dossier", "dossier", "/api/v1/objectives/dossiers/{id}/"),
            ("project_id", "project", "project", "/api/v1/objectives/projects/{id}/"),
            ("personal_asset_id", "resource", "personal_asset", "/api/v1/me/resources/{id}/"),
            ("activity_id", "activity", "activity", "/api/v1/activities/{id}/"),
        )
        for key, target, kind, expected_link in cases:
            with self.subTest(key=key):
                resource_id = str(uuid4())
                navigation = build_notification_navigation(self._notification(**{key: resource_id}))
                self.assertEqual(navigation["schema_version"], 1)
                self.assertEqual(navigation["target"], target)
                self.assertEqual(navigation["resource"], {"kind": kind, "id": resource_id})
                self.assertEqual(navigation["links"]["api"], expected_link.format(id=resource_id))

    def test_event_compatibility_does_not_invent_slug_or_owner_link(self):
        event_id = str(uuid4())
        navigation = build_notification_navigation(self._notification(event_id=event_id))
        self.assertEqual(navigation["target"], "event")
        self.assertEqual(navigation["resource"], {"kind": "event", "id": event_id})
        self.assertNotIn("links", navigation)

    def test_action_url_is_never_parsed_into_structured_navigation(self):
        notification = self._notification()
        notification.action_url = "/me/journeys/not-a-contract/"
        self.assertIsNone(build_notification_navigation(notification))


class M100ShellPrivacyContractTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="m10-shell",
            email="m10-shell@example.com",
            password="M10-shell-strong-password-2026!",
        )
        self.other = User.objects.create_user(
            username="m10-shell-other",
            email="m10-shell-other@example.com",
            password="M10-shell-other-strong-password-2026!",
        )
        self.mine = Notification.objects.create(
            recipient=self.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Ma navigation",
            message="Privée",
            metadata={"journey_id": str(uuid4())},
        )
        self.theirs = Notification.objects.create(
            recipient=self.other,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Navigation tierce",
            message="Ne doit pas fuiter",
            metadata={"access_id": str(uuid4())},
        )
        self.client.force_authenticate(self.user)

    def test_private_shell_reads_are_no_store(self):
        for path in (
            "/api/v1/accounts/auth/me/",
            "/api/v1/accounts/notification-preferences/",
            "/api/v1/notifications/",
            "/api/v1/conversations/",
            "/api/v1/me/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_notification_detail_is_self_scoped_and_navigation_is_structured(self):
        mine = self.client.get(f"/api/v1/notifications/{self.mine.pk}/")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine["Cache-Control"], "private, no-store")
        navigation = mine.json()["navigation"]
        self.assertEqual(navigation["target"], "journey")
        self.assertEqual(
            navigation["links"]["api"],
            f"/api/v1/me/journeys/{self.mine.metadata['journey_id']}/",
        )

        foreign = self.client.get(f"/api/v1/notifications/{self.theirs.pk}/")
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign["Cache-Control"], "private, no-store")
