from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from objectives.models import Dossier, DossierLifecycle, Project, ProjectLifecycle
from tickets.models import TicketWaitlistEntry, WaitlistStatus
from tickets.services import create_order, create_ticket_transfer

from .personal_navigation import personal_surface_owner


User = get_user_model()


class UX2PersonalNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ux2-profile",
            email="ux2-profile@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="ux2-other",
            email="ux2-other@example.test",
            password="StrongPass2026!",
        )
        self.factory = RequestFactory()

    def _owner(self, route_name, *args):
        path = reverse(route_name, args=args)
        request = self.factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return personal_surface_owner(request)

    def test_secondary_surfaces_have_one_personal_owner(self):
        expected = {
            "core:participant-home": "now",
            "discovery:home": "discover",
            "core:makolo-mark": "mark",
            "core:participant-ongoing": "ongoing",
            "core:participant-me": "me",
            "core:participant-accesses": "ongoing",
            "core:participant-history": "me",
            "objectives:dossier-list": "ongoing",
            "objectives:project-list": "ongoing",
            "tickets:waitlist-list": "ongoing",
            "tickets:transfer-list": "ongoing",
            "payments:list": "ongoing",
            "recognition:dashboard": "me",
            "loyalty:dashboard": "me",
            "groups:list": "me",
            "personal_assets:list": "me",
            "conversations:list": "header",
            "notifications:list": "header",
        }
        for route_name, owner in expected.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(self._owner(route_name).owner, owner)

    def test_personal_shell_keeps_same_owner_on_mobile_and_desktop(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("recognition:dashboard"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        mobile = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]
        desktop = html.split('id="desktop-sidebar"', 1)[1].split("</aside>", 1)[0]
        self.assertIn('aria-current="page" class="is-active"', mobile)
        self.assertIn("<span>Moi</span>", mobile)
        self.assertIn('aria-current="page" class="is-active"', desktop)
        self.assertIn("<span>Moi</span>", desktop)
        self.assertIn(reverse("core:participant-me"), html)

    def test_personal_dossier_and_project_are_reachable_from_ongoing(self):
        Dossier.objects.create(
            title="Préparer mon installation",
            created_by=self.user,
            owner_profile=self.user,
            lifecycle=DossierLifecycle.ACTIVE,
        )
        Project.objects.create(
            title="Construire ma trajectoire",
            created_by=self.user,
            owner_profile=self.user,
            lifecycle=ProjectLifecycle.ACTIVE,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-ongoing"))
        self.assertContains(response, "Préparer mon installation")
        self.assertContains(response, "Construire ma trajectoire")
        self.assertContains(response, reverse("objectives:dossier-list"))
        self.assertContains(response, reverse("objectives:project-list"))

    def test_history_no_longer_promotes_numeric_personal_goals(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-history"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Objectifs atteints")
        self.assertNotContains(response, reverse("goals:list"))


class UX2PersonalWaitlistTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ux2-waiter",
            email="ux2-waiter@example.test",
            password="StrongPass2026!",
        )
        self.owner = User.objects.create_user(
            username="ux2-owner",
            email="ux2-owner@example.test",
            password="StrongPass2026!",
        )
        start = timezone.now() + timedelta(days=7)
        self.event = Event.objects.create(
            organizer=self.owner,
            title="UX2 occurrence",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            registration_start_at=timezone.now() - timedelta(hours=1),
            registration_end_at=start,
            capacity=2,
            published_at=timezone.now(),
        )
        self.ticket_type = self.event.ticket_types.create(
            name="UX2 place",
            price="0.00",
            quantity_total=2,
            max_per_order=1,
        )
        self.owner_order = create_order(
            buyer=self.owner,
            event=self.event,
            customer_name="Owner",
            customer_email=self.owner.email,
            selections=[(self.ticket_type, 1)],
        )
        self.client.force_login(self.user)

    def test_waiting_waitlist_stays_out_of_now_but_is_in_ongoing(self):
        TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.user,
            status=WaitlistStatus.WAITING,
        )
        home = self.client.get(reverse("core:participant-home"))
        self.assertNotContains(home, "Une place s’est libérée")
        ongoing = self.client.get(reverse("core:participant-ongoing"))
        self.assertContains(ongoing, "Vous attendez qu’une place se libère.")
        self.assertContains(ongoing, reverse("tickets:waitlist-list"))

    def test_waitlist_offer_is_actionable_now(self):
        TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.user,
            status=WaitlistStatus.OFFERED,
            offered_order=self.owner_order,
            offered_at=timezone.now(),
            offer_expires_at=timezone.now() + timedelta(hours=2),
        )
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, "Une place s’est libérée et attend votre décision.")
        self.assertContains(response, reverse("tickets:waitlist-list"))

    def test_incoming_transfer_is_actionable_now_and_continues(self):
        ticket = self.owner_order.tickets.first()
        transfer = create_ticket_transfer(ticket=ticket, sender=self.owner, recipient_email=self.user.email)
        self.assertTrue(transfer.is_pending_active)

        home = self.client.get(reverse("core:participant-home"))
        self.assertContains(home, "Un transfert de droit vous est proposé.")
        self.assertContains(home, reverse("tickets:transfer-list"))

        ongoing = self.client.get(reverse("core:participant-ongoing"))
        self.assertContains(ongoing, "Un transfert attend votre décision.")
