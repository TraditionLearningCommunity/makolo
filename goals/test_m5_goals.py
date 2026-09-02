from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import Notification

from .models import PersonalGoalStatus, PersonalGoalType
from .selectors import goal_progresses
from .services import create_personal_goal, evaluate_goals, set_goal_status


User = get_user_model()


class M5PersonalGoalTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(username="goal-owner", email="goal-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="goal-other", email="goal-other@example.test", password="StrongPass2026!")
        self.activity = Activity.objects.create(owner_profile=self.profile, created_by=self.profile, title="Goal Activity")
        self.today = timezone.localdate()

    def goal(self, target=2, goal_type=PersonalGoalType.JOURNEYS_COMPLETED):
        return create_personal_goal(
            profile=self.profile,
            goal_type=goal_type,
            target_value=target,
            period_start=self.today - timedelta(days=30),
            period_end=self.today + timedelta(days=30),
        )

    def fulfilled(self, *, activity=None, days_ago=0):
        journey = Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.profile,
            activity=activity or self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        fulfilled_at = timezone.now() - timedelta(days=days_ago)
        Journey.objects.filter(pk=journey.pk).update(status=JourneyStatus.FULFILLED, fulfilled_at=fulfilled_at)
        journey.refresh_from_db()
        return journey

    def test_create_progress_and_idempotent_completion(self):
        goal = self.goal(target=2)
        self.fulfilled()
        self.assertEqual(goal_progresses(self.profile, goals=[goal])[0].current_value, 1)
        self.assertEqual(evaluate_goals(profile=self.profile), [])
        self.fulfilled()
        completed = evaluate_goals(profile=self.profile)
        self.assertEqual([row.pk for row in completed], [goal.pk])
        goal.refresh_from_db()
        self.assertEqual(goal.status, PersonalGoalStatus.COMPLETED)
        self.assertEqual(evaluate_goals(profile=self.profile), [])
        self.assertEqual(Notification.objects.filter(dedup_key=f"goal-completed:{goal.pk}").count(), 1)

    def test_activity_goal_counts_distinct_canonical_activities(self):
        second = Activity.objects.create(owner_profile=self.profile, created_by=self.profile, title="Second Goal Activity")
        goal = self.goal(target=2, goal_type=PersonalGoalType.ACTIVITIES_COMPLETED)
        self.fulfilled(activity=self.activity)
        self.fulfilled(activity=self.activity)
        self.fulfilled(activity=second)
        self.assertEqual(goal_progresses(self.profile, goals=[goal])[0].current_value, 2)

    def test_pause_cancel_and_owner_boundary(self):
        goal = self.goal()
        set_goal_status(actor=self.profile, goal=goal, status=PersonalGoalStatus.PAUSED)
        goal.refresh_from_db()
        self.assertEqual(goal.status, PersonalGoalStatus.PAUSED)
        with self.assertRaises(PermissionDenied):
            set_goal_status(actor=self.other, goal=goal, status=PersonalGoalStatus.CANCELLED)
        set_goal_status(actor=self.profile, goal=goal, status=PersonalGoalStatus.CANCELLED)
        goal.refresh_from_db()
        self.assertEqual(goal.status, PersonalGoalStatus.CANCELLED)

    def test_target_and_period_validation(self):
        with self.assertRaises(ValidationError):
            create_personal_goal(
                profile=self.profile,
                goal_type=PersonalGoalType.JOURNEYS_COMPLETED,
                target_value=0,
                period_start=self.today,
                period_end=self.today,
            )
        with self.assertRaises(ValidationError):
            create_personal_goal(
                profile=self.profile,
                goal_type=PersonalGoalType.JOURNEYS_COMPLETED,
                target_value=1,
                period_start=self.today,
                period_end=self.today - timedelta(days=1),
            )

    def test_progress_projection_is_bounded_and_not_a_counter_on_goal(self):
        goals = [self.goal(target=index + 1) for index in range(3)]
        self.fulfilled()
        with self.assertNumQueries(1):
            progresses = goal_progresses(self.profile, goals=goals)
        self.assertEqual([item.current_value for item in progresses], [1, 1, 1])
        self.assertFalse(hasattr(goals[0], "progress_count"))
