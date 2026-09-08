import unittest

from universe_sim.examples import construire_etoile_binaire, construire_systeme_solaire_complet, construire_systeme_terre_lune


class ExtendedExampleTests(unittest.TestCase):
    def test_full_solar_scene_contains_eight_planets_and_moon(self):
        simulation = construire_systeme_solaire_complet()
        noms = {corps.nom for corps in simulation.univers.corps_physiques}
        self.assertEqual(
            noms,
            {"Soleil", "Mercure", "Venus", "Terre", "Lune", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune"},
        )

    def test_earth_moon_scene_is_barycentric(self):
        simulation = construire_systeme_terre_lune()
        terre = simulation.univers.trouver_corps("Terre")
        lune = simulation.univers.trouver_corps("Lune")
        etat_terre = terre.etat().translation
        etat_lune = lune.etat().translation
        self.assertIsNotNone(etat_terre)
        self.assertIsNotNone(etat_lune)
        centre_x = (
            terre.masse().value * etat_terre.position.x + lune.masse().value * etat_lune.position.x
        ) / (terre.masse().value + lune.masse().value)
        self.assertLess(abs(centre_x), 1e-6)

    def test_binary_scene_has_two_stars(self):
        simulation = construire_etoile_binaire()
        self.assertEqual({corps.nom for corps in simulation.univers.corps_physiques}, {"Alpha", "Beta"})
