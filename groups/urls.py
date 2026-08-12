from django.urls import path

from .views import (
    GroupAddMemberView,
    GroupArchiveView,
    GroupCreateView,
    GroupDetailView,
    GroupEditView,
    GroupImportView,
    GroupInvitationClaimView,
    GroupInviteView,
    GroupLeaveView,
    GroupListView,
    GroupMembersView,
    GroupRemoveMemberView,
    GroupResponsibilityView,
    GroupRevokeInvitationView,
    GroupSnapshotCreateView,
    GroupSuspendMemberView,
    GroupTransferOwnershipView,
)


app_name = "groups"

urlpatterns = [
    path("", GroupListView.as_view(), name="list"),
    path("new/", GroupCreateView.as_view(), name="create"),
    path("invitations/<str:token>/", GroupInvitationClaimView.as_view(), name="invitation"),
    path("<slug:slug>/", GroupDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", GroupEditView.as_view(), name="edit"),
    path("<slug:slug>/members/", GroupMembersView.as_view(), name="members"),
    path("<slug:slug>/members/add/", GroupAddMemberView.as_view(), name="member-add"),
    path("<slug:slug>/members/<uuid:profile_id>/suspend/", GroupSuspendMemberView.as_view(), name="member-suspend"),
    path("<slug:slug>/members/<uuid:profile_id>/remove/", GroupRemoveMemberView.as_view(), name="member-remove"),
    path("<slug:slug>/leave/", GroupLeaveView.as_view(), name="leave"),
    path("<slug:slug>/invite/", GroupInviteView.as_view(), name="invite"),
    path("<slug:slug>/invitations/<uuid:invitation_id>/revoke/", GroupRevokeInvitationView.as_view(), name="invitation-revoke"),
    path("<slug:slug>/import/", GroupImportView.as_view(), name="import"),
    path("<slug:slug>/snapshots/create/", GroupSnapshotCreateView.as_view(), name="snapshot-create"),
    path("<slug:slug>/archive/", GroupArchiveView.as_view(), name="archive"),
    path("<slug:slug>/transfer/", GroupTransferOwnershipView.as_view(), name="transfer"),
    path("<slug:slug>/responsibilities/", GroupResponsibilityView.as_view(), name="responsibility"),
]
