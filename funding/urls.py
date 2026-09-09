from django.urls import path

from .views import FundingContributeView, FundingCreateView, FundingDetailView, FundingManageView


app_name = "funding"

urlpatterns = [
    path("new/", FundingCreateView.as_view(), name="create"),
    path("<uuid:pk>/", FundingDetailView.as_view(), name="detail"),
    path("<uuid:pk>/manage/", FundingManageView.as_view(), name="manage"),
    path("<uuid:pk>/contribute/", FundingContributeView.as_view(), name="contribute"),
]
