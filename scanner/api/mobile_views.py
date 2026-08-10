from rest_framework import generics, permissions

from scanner.selectors import get_current_assignments_visible_to

from .serializers import ScannerAssignmentSerializer


class CurrentScannerAssignmentListAPIView(generics.ListAPIView):
    """Current scanner assignments for the authenticated mobile client."""

    serializer_class = ScannerAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return get_current_assignments_visible_to(self.request.user).order_by(
            "event__start_at",
            "label",
        )
