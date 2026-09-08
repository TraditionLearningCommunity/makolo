import unittest

from universe_sim.examples import construire_systeme_solaire_complet, construire_systeme_terre_lune
from universe_sim.visuals import capturer_sequence, construire_plan_camera, obtenir_echelle


class VisualLayerTests(unittest.TestCase):
    def test_capture_hits_requested_final_step(self):
        simulation = construire_systeme_terre_lune(dt=900.0)
        sequence = capturer_sequence(simulation, pas_total=8, frames=5)
        self.assertEqual(len(sequence.frames), 5)
        self.assertEqual(sequence.pas_total, 8)
        self.assertEqual(sequence.frames[-1].instant_s, 8 * 900.0)

    def test_orbit_camera_follows_earth_at_multiscale(self):
        simulation = construire_systeme_terre_lune(dt=900.0)
        sequence = capturer_sequence(simulation, pas_total=4, frames=3)
        plan = construire_plan_camera(sequence, obtenir_echelle("earth-moon"), focus="Terre", mode="orbit")
        terre_id = sequence.trouver_id("Terre")
        self.assertEqual(len(plan), len(sequence.frames))
        for index, camera in enumerate(plan):
            self.assertEqual(camera.centre, sequence.frames[index].positions[terre_id])
            self.assertEqual(camera.span_m, 5.5e8)

    def test_cinematic_tour_zooms_in_for_full_solar_scene(self):
        simulation = construire_systeme_solaire_complet(dt=21_600.0)
        sequence = capturer_sequence(simulation, pas_total=4, frames=5)
        plan = construire_plan_camera(sequence, obtenir_echelle("solar"), mode="tour")
        self.assertEqual(len(plan), 5)
        self.assertLess(plan[-1].span_m, plan[0].span_m)
