from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PersonalGoal
from .selectors import goal_progresses, goals_for_profile
from .services import create_personal_goal, evaluate_goals, set_goal_status


class GoalsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        evaluate_goals(profile=request.user)
        progresses = goal_progresses(request.user, goals=goals_for_profile(request.user))
        return Response({"results": [{
            "id": str(item.goal.pk), "goal_type": item.goal.goal_type, "status": item.goal.status,
            "target_value": item.target_value, "current_value": item.current_value, "percent": item.percent,
            "period_start": item.goal.period_start, "period_end": item.goal.period_end,
        } for item in progresses]})

    def post(self, request):
        try:
            goal = create_personal_goal(
                profile=request.user,
                goal_type=request.data.get("goal_type", ""),
                target_value=int(request.data.get("target_value", 0)),
                period_start=date.fromisoformat(str(request.data.get("period_start", ""))),
                period_end=date.fromisoformat(str(request.data.get("period_end", ""))),
            )
        except (ValueError, ValidationError) as exc:
            return Response({"detail": getattr(exc, "message_dict", None) or str(exc)}, status=400)
        return Response({"id": str(goal.pk), "status": goal.status}, status=201)


class GoalStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        goal = get_object_or_404(PersonalGoal, pk=pk)
        try:
            goal = set_goal_status(actor=request.user, goal=goal, status=request.data.get("status", ""))
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=403)
        except ValidationError as exc:
            return Response({"detail": getattr(exc, "message_dict", None) or str(exc)}, status=400)
        return Response({"id": str(goal.pk), "status": goal.status})
