import unittest

from universe_sim.events import TypeEvenement, TypeEvenementSimulation


class EventTaxonomyTests(unittest.TestCase):
    def test_horizon_crossing_is_a_physical_event(self):
        self.assertEqual(TypeEvenement.FRANCHISSEMENT_HORIZON.value, "franchissement_horizon")

    def test_lod_materialization_is_a_simulation_event(self):
        self.assertEqual(TypeEvenementSimulation.MATERIALISATION_LOD.value, "materialisation_lod")
        self.assertNotIn("materialisation_lod", {event.value for event in TypeEvenement})


if __name__ == "__main__":
    unittest.main()
