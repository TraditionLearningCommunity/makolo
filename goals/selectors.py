from dataclasses import dataclass
from datetime import datetime, time

from django.utils import timezone

from journeys.models import Journey, JourneyStatus

from .models import PersonalGoal, PersonalGoalStatus, PersonalGoalType


MAX_GOALS_PER_PROJECTION = 100


@dataclass(frozen=True)
class GoalProgress:
    goal: PersonalGoal
    current_value: int
    target_value: int

    @property
    def complete(self):
        return self.current_value >= self.target_value

    @property
    def percent(self):
        return min(100, int((self.current_value / self.target_value) * 100)) if self.target_value else 0


def goals_for_profile(profile, *, include_cancelled=True):
    queryset = PersonalGoal.objects.filter(profile=profile)
    if not include_cancelled:
        queryset = queryset.exclude(status=PersonalGoalStatus.CANCELLED)
    return queryset


def _aware_day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())


def _aware_day_end(day):
    return timezone.make_aware(datetime.combine(day, time.max), timezone.get_current_timezone())


def goal_progresses(profile, *, goals=None):
    rows = list((goals if goals is not None else goals_for_profile(profile))[:MAX_GOALS_PER_PROJECTION])
    if not rows:
        return []
    period_start = min(goal.period_start for goal in rows)
    period_end = max(goal.period_end for goal in rows)
    facts = list(
        Journey.objects.filter(
            beneficiary=profile,
            status=JourneyStatus.FULFILLED,
            fulfilled_at__gte=_aware_day_start(period_start),
            fulfilled_at__lte=_aware_day_end(period_end),
        ).values_list("fulfilled_at", "activity_id")
    )
    projected = []
    for goal in rows:
        start = _aware_day_start(goal.period_start)
        end = _aware_day_end(goal.period_end)
        in_period = [(fulfilled_at, activity_id) for fulfilled_at, activity_id in facts if fulfilled_at and start <= fulfilled_at <= end]
        if goal.goal_type == PersonalGoalType.ACTIVITIES_COMPLETED:
            current = len({activity_id for _, activity_id in in_period})
        else:
            current = len(in_period)
        projected.append(GoalProgress(goal=goal, current_value=current, target_value=goal.target_value))
    return projected
