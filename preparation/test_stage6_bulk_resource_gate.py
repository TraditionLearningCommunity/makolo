"""Stage 6: bulk Group gate input must preserve Preparation's deny-by-default rules."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from preparation.services import _public_activity_resource_allowed


class PublicResourceBulkEligibilityTests(SimpleTestCase):
    def _activity(self):
        from activities.models import ActivityStatus, ActivityVisibility

        return SimpleNamespace(
            pk=42,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
            space_id=3,
            space=SimpleNamespace(
                public_profile=True, searchable=True,
                lifecycle="active", verification_status="unverified",
            ),
        )

    def test_bulk_gate_rejects_non_admitted_public_activity(self):
        activity = self._activity()
        with patch("groups.selectors.eligible_activity_ids_for_profile") as lookup:
            self.assertFalse(_public_activity_resource_allowed(
                None, activity, eligible_activity_ids=set(),
            ))
            lookup.assert_not_called()

    def test_bulk_gate_retains_public_owner_conditions(self):
        activity = self._activity()
        activity.space.searchable = False
        with patch("groups.selectors.eligible_activity_ids_for_profile") as lookup:
            self.assertFalse(_public_activity_resource_allowed(
                None, activity, eligible_activity_ids={"42"},
            ))
            lookup.assert_not_called()

    def test_existing_nonbulk_path_still_checks_group_eligibility(self):
        activity = self._activity()
        with patch("groups.selectors.eligible_activity_ids_for_profile", return_value=set()) as lookup:
            self.assertFalse(_public_activity_resource_allowed(None, activity))
            lookup.assert_called_once_with(None, [42])
