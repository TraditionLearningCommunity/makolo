from django.test import SimpleTestCase

from core.personal_surface_orchestration import (
    pass_discovery_candidates_through_molongo,
    pass_now_candidates_through_molongo,
    pass_ongoing_candidates_through_molongo,
)


class PersonalSurfaceMolongoSeamTests(SimpleTestCase):
    def test_current_seams_are_strict_pass_throughs(self):
        now = ("now-a", "now-b")
        ongoing = ("ongoing-a",)
        discovery = ("discover-a", "discover-b")

        self.assertIs(pass_now_candidates_through_molongo(now), now)
        self.assertIs(pass_ongoing_candidates_through_molongo(ongoing), ongoing)
        self.assertIs(pass_discovery_candidates_through_molongo(discovery), discovery)
