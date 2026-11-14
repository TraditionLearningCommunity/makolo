from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from notifications.models import Notification, NotificationCategory, NotificationKind


class NotificationInboxFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="notification-owner", password="secret")
        self.other = user_model.objects.create_user(username="notification-foreign", password="secret")
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        for index in range(34):
            Notification.objects.create(
                recipient=self.user,
                category=NotificationCategory.SYSTEM,
                kind=NotificationKind.SYSTEM,
                title=f"Information {index}",
                message="Information consultable.",
            )
        for index in range(3):
            Notification.objects.create(
                recipient=self.other,
                title=f"Privé {index}",
                message="Contenu privé.",
            )

    def test_cursor_is_invisible_but_complete_without_duplicates(self):
        url = "/api/v1/notifications/"
        ids = []
        counts = []
        while url:
            result = self.api.get(url)
            self.assertEqual(result.status_code, 200)
            counts.append(len(result.data["results"]))
            self.assertEqual(result.data["total_count"], 34)
            self.assertEqual(result.data["unread_count"], 34)
            ids.extend(item["id"] for item in result.data["results"])
            next_url = result.data["next"]
            url = urlsplit(next_url).path + "?" + urlsplit(next_url).query if next_url else None
        self.assertEqual(counts, [15, 15, 4])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 34)

    def test_read_counts_change_without_deleting_notifications(self):
        first = self.api.get("/api/v1/notifications/").data["results"][0]["id"]
        marked = self.api.post(f"/api/v1/notifications/{first}/read/")
        self.assertEqual(marked.status_code, 200)
        state = self.api.get("/api/v1/notifications/").data
        self.assertEqual(state["total_count"], 34)
        self.assertEqual(state["unread_count"], 33)
        filtered = self.api.get("/api/v1/notifications/?filter=unread").data
        self.assertEqual(filtered["count"], 33)
        self.assertEqual(filtered["total_count"], 34)

    def test_unread_continuation_uses_filtered_count_across_all_pages(self):
        first = self.api.get("/api/v1/notifications/").data["results"][0]["id"]
        self.assertEqual(
            self.api.post(f"/api/v1/notifications/{first}/read/").status_code, 200
        )
        url = "/api/v1/notifications/?filter=unread"
        seen = set()
        page_sizes = []
        while url:
            result = self.api.get(url)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.data["count"], 33)
            self.assertEqual(result.data["total_count"], 34)
            page_sizes.append(len(result.data["results"]))
            for row in result.data["results"]:
                self.assertFalse(row["is_read"])
                self.assertNotIn(row["id"], seen)
                seen.add(row["id"])
            next_url = result.data["next"]
            url = (
                urlsplit(next_url).path + "?" + urlsplit(next_url).query
                if next_url else None
            )
            if url:
                self.assertIn("filter=unread", url)
        self.assertEqual(page_sizes, [15, 15, 3])
        self.assertEqual(len(seen), 33)

    def test_owners_and_web_infinite_scroll_contract(self):
        self.api.force_authenticate(self.other)
        response = self.api.get("/api/v1/notifications/")
        self.assertEqual(response.data["total_count"], 3)
        self.assertEqual(response.data["unread_count"], 3)
        self.client.force_login(self.user)
        web = self.client.get("/notifications/")
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "data-notification-sentinel")
        self.assertContains(web, "notifications-inbox.js")
        self.assertNotContains(web, "Page 1")
        self.assertNotContains(web, "Suivant")
