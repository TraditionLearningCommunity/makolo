from django.urls import path

from .views import (
    ActionNeedCloseView,
    ActionNeedDetailView,
    ActionNeedSolicitView,
    ActionNeedsView,
    GroupContributeView,
    GroupNetworkView,
    GroupShareActivityView,
    NetworkView,
    ProfileSolicitationCancelView,
    ProfileSolicitationRespondView,
    ProfileSolicitationsView,
    RemoveContributionView,
    ReplyContributionView,
)

app_name = "social"
urlpatterns = [
    path("network/", NetworkView.as_view(), name="network"),
    path("network/groups/<slug:slug>/", GroupNetworkView.as_view(), name="group"),
    path("network/groups/<slug:slug>/contribute/", GroupContributeView.as_view(), name="group-contribute"),
    path("network/groups/<slug:slug>/share/", GroupShareActivityView.as_view(), name="group-share"),
    path("network/contributions/<uuid:pk>/reply/", ReplyContributionView.as_view(), name="reply"),
    path("network/contributions/<uuid:pk>/remove/", RemoveContributionView.as_view(), name="remove"),
    path("network/needs/", ActionNeedsView.as_view(), name="needs"),
    path("network/needs/<uuid:pk>/", ActionNeedDetailView.as_view(), name="need-detail"),
    path("network/needs/<uuid:pk>/close/", ActionNeedCloseView.as_view(), name="need-close"),
    path("network/needs/<uuid:pk>/solicit/<uuid:profile_id>/", ActionNeedSolicitView.as_view(), name="need-solicit"),
    path("network/solicitations/", ProfileSolicitationsView.as_view(), name="my-solicitations"),
    path("network/solicitations/<uuid:pk>/respond/", ProfileSolicitationRespondView.as_view(), name="solicitation-respond"),
    path("network/solicitations/<uuid:pk>/cancel/", ProfileSolicitationCancelView.as_view(), name="solicitation-cancel"),
]
