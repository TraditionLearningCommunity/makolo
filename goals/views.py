from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .models import PersonalGoal, PersonalGoalType
from .selectors import goal_progresses, goals_for_profile
from .services import create_personal_goal, evaluate_goals, set_goal_status


class GoalListView(LoginRequiredMixin, TemplateView):
    template_name = "goals/list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        evaluate_goals(profile=self.request.user)
        goals = goals_for_profile(self.request.user)
        context["progresses"] = goal_progresses(self.request.user, goals=goals)
        context["goal_types"] = PersonalGoalType.choices
        context["today"] = date.today()
        return context


class GoalCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request):
        try:
            create_personal_goal(
                profile=request.user,
                goal_type=request.POST.get("goal_type", ""),
                target_value=int(request.POST.get("target_value", "0")),
                period_start=date.fromisoformat(request.POST.get("period_start", "")),
                period_end=date.fromisoformat(request.POST.get("period_end", "")),
            )
        except (ValueError, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Objectif personnel créé. Sa progression vient des faits Makolo.")
        return redirect("goals:list")


class GoalStatusView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        goal = get_object_or_404(PersonalGoal, pk=pk)
        try:
            set_goal_status(actor=request.user, goal=goal, status=request.POST.get("status", ""))
        except PermissionDenied:
            raise PermissionDenied("Cet objectif personnel ne vous appartient pas.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Objectif mis à jour.")
        return redirect("goals:list")
