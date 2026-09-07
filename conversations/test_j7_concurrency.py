from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization

from .contact_models import ContactPolicyMode, ProfileContactPolicy
from .contact_services import ensure_direct_conversation
from .core_models import ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point, resolve_point, submit_point_response
from .services import ensure_context_conversation


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "J7 concurrency requires PostgreSQL row locking.")
class ConversationConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    serialized_rollback = True

    def setUp(self):
        self.owner = User.objects.create_user(username="j7-concurrency-owner", email="j7-concurrency-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j7-concurrency-member", email="j7-concurrency-member@example.test", password="StrongPass2026!")
        self.rep_a = User.objects.create_user(username="j7-concurrency-rep-a", email="j7-concurrency-rep-a@example.test", password="StrongPass2026!")
        self.rep_b = User.objects.create_user(username="j7-concurrency-rep-b", email="j7-concurrency-rep-b@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J7 Concurrency Space", created_by=self.owner)
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner, source="j7-concurrency")
        grant_space_role(profile=self.member, space=self.space, role=SystemRoleCode.SPACE_COMMUNICATION_MANAGER, granted_by=self.owner, source="j7-concurrency")
        grant_space_role(profile=self.rep_a, space=self.space, role=SystemRoleCode.SPACE_COMMUNICATION_MANAGER, granted_by=self.owner, source="j7-concurrency")
        grant_space_role(profile=self.rep_b, space=self.space, role=SystemRoleCode.SPACE_COMMUNICATION_MANAGER, granted_by=self.owner, source="j7-concurrency")
        self.conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.SPACE,
            space=self.space,
        )

    def _thread(self, barrier, fn):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return fn()
        finally:
            connection.close()

    def test_duplicate_mobile_response_converges_on_same_response(self):
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Réponse idempotente",
        )
        barrier = Barrier(2)

        def submit():
            actor = User.objects.get(pk=self.member.pk)
            current = type(point).objects.get(pk=point.pk)
            response = submit_point_response(
                actor=actor,
                point=current,
                value="Même réponse",
                client_reference="j7-concurrent-mobile-response",
            )
            return str(response.pk)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._thread, barrier, submit) for _ in range(2)]
            ids = [future.result(timeout=10) for future in futures]
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(point.responses.count(), 1)

    def test_two_representatives_cannot_cast_two_active_space_votes(self):
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Vote de l’Espace",
        )
        barrier = Barrier(2)

        def submit(profile_id, value):
            actor = User.objects.get(pk=profile_id)
            current = type(point).objects.get(pk=point.pk)
            represented_space = Organization.objects.get(pk=self.space.pk)
            try:
                response = submit_point_response(
                    actor=actor,
                    point=current,
                    value=value,
                    represented_space=represented_space,
                )
                return ("ok", str(response.pk))
            except ValidationError:
                return ("rejected", None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self._thread, barrier, lambda: submit(self.rep_a.pk, "A")),
                pool.submit(self._thread, barrier, lambda: submit(self.rep_b.pk, "B")),
            ]
            outcomes = [future.result(timeout=10) for future in futures]
        self.assertEqual([state for state, _ in outcomes].count("ok"), 1)
        self.assertEqual([state for state, _ in outcomes].count("rejected"), 1)
        self.assertEqual(point.responses.filter(status="active", represented_space=self.space).count(), 1)

    def test_double_resolution_returns_single_resolution(self):
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Résolution concurrente",
        )
        barrier = Barrier(2)

        def resolve():
            actor = User.objects.get(pk=self.owner.pk)
            current = type(point).objects.get(pk=point.pk)
            resolution = resolve_point(actor=actor, point=current, summary="Résultat canonique")
            return str(resolution.pk)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._thread, barrier, resolve) for _ in range(2)]
            ids = [future.result(timeout=10) for future in futures]
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(type(point).objects.get(pk=point.pk).lifecycle, "resolved")

    def test_duplicate_direct_conversation_converges(self):
        target = User.objects.create_user(username="j7-direct-target", email="j7-direct-target@example.test", password="StrongPass2026!")
        ProfileContactPolicy.objects.create(profile=target, mode=ContactPolicyMode.DIRECT)
        barrier = Barrier(2)

        def ensure():
            actor = User.objects.get(pk=self.owner.pk)
            other = User.objects.get(pk=target.pk)
            return str(ensure_direct_conversation(actor=actor, target=other).pk)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._thread, barrier, ensure) for _ in range(2)]
            ids = [future.result(timeout=10) for future in futures]
        self.assertEqual(len(set(ids)), 1)
