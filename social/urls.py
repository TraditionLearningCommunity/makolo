from django.urls import path

from .views import GroupContributeView, GroupNetworkView, GroupShareActivityView, NetworkView, RemoveContributionView, ReplyContributionView

app_name = "social"
urlpatterns = [
    path("network/", NetworkView.as_view(), name="network"),
    path("network/groups/<slug:slug>/", GroupNetworkView.as_view(), name="group"),
    path("network/groups/<slug:slug>/contribute/", GroupContributeView.as_view(), name="group-contribute"),
    path("network/groups/<slug:slug>/share/", GroupShareActivityView.as_view(), name="group-share"),
    path("network/contributions/<uuid:pk>/reply/", ReplyContributionView.as_view(), name="reply"),
    path("network/contributions/<uuid:pk>/remove/", RemoveContributionView.as_view(), name="remove"),
]
