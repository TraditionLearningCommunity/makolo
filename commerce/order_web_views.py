from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView

from commerce.models import CommerceOrder


class PersonalCommerceOrderWebDetailView(LoginRequiredMixin, DetailView):
    template_name = "commerce/personal_order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return CommerceOrder.objects.filter(
            buyer=self.request.user,
        ).select_related("journey__activity")
