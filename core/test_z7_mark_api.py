from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.services import issue_access
from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from discovery.models import ActivityBookmark, DiscoveryWatch
from journeys.models import Journey, JourneyStatus, WorkflowKind
from topics.models import ProfileInterest
from recognition.models import RecognitionRedemption, RewardDefinition, RewardKind
from recognition.services import get_or_create_account


PASSWORD = "Makolo!2026-Z7-MarkA8"


class Z7MakoloMarkAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = self._user("z7-mark-user")
        self.other = self._user("z7-mark-other")
        self.activity = Activity.objects.create(
            title="Candidature Z7",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )

    def _user(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@makolo.test",
            password=PASSWORD,
        )

    def _post(self, text, *, context=None):
        return self.client.post(
            "/api/v1/me/mark/",
            {
                "input": {"kind": "text", "value": text},
                "context": context or {},
            },
            format="json",
        )

    def test_mark_requires_authentication_and_uses_z_envelope(self):
        response = self._post("Trouve une bourse")
        self.assertEqual(response.status_code, 401)

        self.client.force_authenticate(self.user)
        response = self._post("Trouve une bourse")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["projection"], "personal.mark")
        self.assertEqual(payload["meta"]["scope"], "personal")
        self.assertEqual(payload["data"]["state"], "resolved")

    def test_open_search_routes_to_discover_without_mutation(self):
        self.client.force_authenticate(self.user)

        response = self._post("Trouve une bourse")
        data = response.json()["data"]

        self.assertEqual(data["understanding"]["intent"], "discover_search")
        self.assertEqual(data["handoff"]["owner"], "discovery")
        self.assertIn("/api/v1/discovery/items/?q=", data["links"]["collection"])
        self.assertFalse(ActivityBookmark.objects.filter(user=self.user).exists())
        self.assertFalse(DiscoveryWatch.objects.filter(owner=self.user).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())
        self.assertFalse(Journey.objects.filter(beneficiary=self.user).exists())

    def test_retrieve_saved_does_not_become_open_search(self):
        self.client.force_authenticate(self.user)

        response = self._post("Retrouve la bourse que j'avais sauvegardée")
        data = response.json()["data"]

        self.assertEqual(data["understanding"]["intent"], "retrieve_saved")
        self.assertEqual(data["handoff"]["surface"], "saved")
        self.assertEqual(data["links"]["detail"], "/api/v1/me/considerations/")

    def test_history_and_passport_route_to_existing_personal_surfaces(self):
        self.client.force_authenticate(self.user)

        history = self._post("Retrouve mon historique").json()["data"]
        self.assertEqual(history["understanding"]["intent"], "retrieve_history")
        self.assertEqual(history["links"]["detail"], "/api/v1/me/history/")

        passport = self._post("Montre mon passeport").json()["data"]
        self.assertEqual(passport["understanding"]["intent"], "retrieve_passport")
        self.assertEqual(passport["links"]["detail"], "/api/v1/me/passport/")

    def test_recognition_redemption_requires_confirmation_and_reuses_owner_idempotence(self):
        account = get_or_create_account(profile=self.user)
        account.points_balance = 100
        account.lifetime_earned = 100
        account.save(
            update_fields=["points_balance", "lifetime_earned", "updated_at"]
        )
        reward = RewardDefinition.objects.create(
            code="z7-mark-reward",
            version=1,
            name="Reward Z7",
            kind=RewardKind.OTHER,
            points_cost=20,
            beneficiary_allowed=True,
            fulfillment={"owner_domain": "z7-test"},
        )
        selected = {
            "selected": {
                "kind": "recognition_reward",
                "id": str(reward.pk),
            }
        }
        self.client.force_authenticate(self.user)

        pending = self._post("Utilise cette récompense", context=selected)
        pending_data = pending.json()["data"]
        self.assertEqual(pending_data["state"], "needs_confirmation")
        self.assertEqual(pending_data["action"]["code"], "redeem_recognition")
        self.assertEqual(RecognitionRedemption.objects.count(), 0)

        context = {
            **selected,
            "confirmation": {
                "code": "redeem_recognition",
                "target_id": str(reward.pk),
            },
            "idempotency_key": "z7-mark-redeem-1",
        }
        first = self._post("Utilise cette récompense", context=context)
        second = self._post("Utilise cette récompense", context=context)
        first_data = first.json()["data"]
        second_data = second.json()["data"]

        self.assertEqual(first_data["state"], "completed")
        self.assertEqual(second_data["state"], "completed")
        self.assertEqual(
            first_data["result"]["redemption"]["id"],
            second_data["result"]["redemption"]["id"],
        )
        self.assertEqual(
            RecognitionRedemption.objects.filter(owner_account=account).count(),
            1,
        )
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 80)

    def test_access_retrieve_is_personal_and_foreign_context_does_not_leak(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now(),
            status=OccurrenceStatus.SCHEDULED,
        )
        mine = issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=occurrence,
            source_key="z7:mine",
        )
        foreign = issue_access(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=occurrence,
            source_key="z7:foreign",
        )
        self.client.force_authenticate(self.user)

        response = self._post("Retrouve mon accès")
        data = response.json()["data"]
        self.assertEqual(data["result"]["id"], str(mine.pk))
        self.assertNotIn(str(foreign.pk), response.content.decode())

        response = self._post(
            "Retrouve mon accès",
            context={"selected": {"kind": "access", "id": str(foreign.pk)}},
        )
        data = response.json()["data"]
        self.assertEqual(data["state"], "unknown")
        self.assertNotIn(str(foreign.pk), response.content.decode())

    def test_two_personal_journeys_require_bounded_clarification(self):
        first = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        second_activity = Activity.objects.create(
            title="Deuxième candidature Z7",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        second = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=second_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        self.client.force_authenticate(self.user)

        response = self._post("Ouvre ma candidature")
        data = response.json()["data"]

        self.assertEqual(data["state"], "needs_clarification")
        self.assertEqual(data["question"]["code"], "which_journey")
        ids = {row["id"] for row in data["question"]["options"]}
        self.assertEqual(ids, {str(first.pk), str(second.pk)})
        self.assertLessEqual(len(data["question"]["options"]), 5)

    def test_context_spoofing_cannot_grant_space_or_profile_authority(self):
        self.client.force_authenticate(self.user)

        response = self._post(
            "Ouvre ma candidature",
            context={
                "space_id": "00000000-0000-0000-0000-000000000001",
                "profile_id": str(self.other.pk),
                "role": "owner",
            },
        )
        data = response.json()["data"]

        self.assertEqual(data["state"], "forbidden")
        self.assertEqual(data["result"]["reason"], "personal_scope_only")
        self.assertNotIn(str(self.other.pk), response.content.decode())

    def test_bookmark_mutation_is_explicit_idempotent_and_does_not_create_watch_interest_or_journey(self):
        Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now(),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.user)
        context = {
            "selected": {
                "kind": "discovery_item",
                "family": "activity",
                "id": str(self.activity.pk),
            }
        }

        first = self._post("Garde cette possibilité", context=context)
        second = self._post("Garde cette possibilité", context=context)

        self.assertEqual(first.json()["data"]["state"], "completed")
        self.assertEqual(second.json()["data"]["state"], "completed")
        self.assertEqual(
            ActivityBookmark.objects.filter(
                user=self.user,
                activity=self.activity,
            ).count(),
            1,
        )
        self.assertFalse(DiscoveryWatch.objects.filter(owner=self.user).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())
        self.assertFalse(Journey.objects.filter(beneficiary=self.user).exists())

    def test_watch_creation_is_idempotent_and_distinct_from_bookmark_interest_and_journey(self):
        self.client.force_authenticate(self.user)
        context = {"search": {"q": "bourse"}}

        first = self._post("Continue à chercher ça", context=context)
        second = self._post("Continue à chercher ça", context=context)

        self.assertEqual(first.json()["data"]["result"]["effect"], "watch_created")
        self.assertEqual(
            second.json()["data"]["result"]["effect"],
            "watch_already_active",
        )
        self.assertEqual(
            DiscoveryWatch.objects.filter(owner=self.user).count(),
            1,
        )
        self.assertFalse(ActivityBookmark.objects.filter(user=self.user).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())
        self.assertFalse(Journey.objects.filter(beneficiary=self.user).exists())

    def test_personal_asset_phrase_does_not_create_empty_asset_or_satisfy_requirement(self):
        from personal_assets.models import PersonalAsset

        self.client.force_authenticate(self.user)
        response = self._post("Garde ce document comme ressource")
        data = response.json()["data"]

        self.assertEqual(data["state"], "unsupported")
        self.assertEqual(data["result"]["reason"], "file_ingestion_not_exposed")
        self.assertFalse(PersonalAsset.objects.filter(controller=self.user).exists())

    def test_live_context_is_participant_scoped(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now(),
            status=OccurrenceStatus.SCHEDULED,
        )
        issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=occurrence,
            source_key="z7:live",
        )
        foreign_activity = Activity.objects.create(
            title="Occurrence étrangère Z7",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        foreign_occurrence = Occurrence.objects.create(
            activity=foreign_activity,
            start_at=timezone.now(),
            status=OccurrenceStatus.SCHEDULED,
        )
        issue_access(
            beneficiary=self.other,
            activity=foreign_activity,
            occurrence=foreign_occurrence,
            source_key="z7:live:foreign",
        )
        self.client.force_authenticate(self.user)

        response = self._post(
            "Je suis arrivé",
            context={"occurrence_id": str(occurrence.pk)},
        )
        self.assertEqual(response.json()["data"]["state"], "resolved")
        self.assertIn(
            str(occurrence.pk),
            response.json()["data"]["links"]["live"],
        )

        response = self._post(
            "Je suis arrivé",
            context={"occurrence_id": str(foreign_occurrence.pk)},
        )
        data = response.json()["data"]
        self.assertEqual(data["state"], "unknown")
        self.assertNotIn(str(foreign_occurrence.pk), response.content.decode())

    def test_unsupported_and_ambiguous_requests_are_honest(self):
        self.client.force_authenticate(self.user)

        unsupported = self._post("Négocie automatiquement le prix avec l'organisateur")
        self.assertEqual(unsupported.json()["data"]["state"], "unsupported")

        ambiguous = self._post("Ouvre mon truc")
        self.assertEqual(
            ambiguous.json()["data"]["state"],
            "needs_clarification",
        )

    def test_interpretation_only_request_does_not_mutate_domains(self):
        self.client.force_authenticate(self.user)

        response = self._post("J'ai reçu quelque chose, qu'est-ce que ça veut dire ?")
        self.assertEqual(
            response.json()["data"]["state"],
            "needs_clarification",
        )
        self.assertFalse(ActivityBookmark.objects.filter(user=self.user).exists())
        self.assertFalse(DiscoveryWatch.objects.filter(owner=self.user).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())
        self.assertFalse(Journey.objects.filter(beneficiary=self.user).exists())

    def test_non_text_modality_is_unsupported_without_persistence(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/me/mark/",
            {
                "input": {"kind": "file_reference", "value": "opaque-client-ref"},
                "context": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["state"], "unsupported")
