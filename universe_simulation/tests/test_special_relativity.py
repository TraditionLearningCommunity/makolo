import unittest

from universe_sim.constants import C
from universe_sim.relativistic_values import (
    facteur_lorentz,
    impulsion_relativiste,
    quadrimpulsion_depuis_vitesse,
    vitesse_depuis_impulsion,
)
from universe_sim.services.relativistic_geometry import (
    EvenementMinkowski,
    transformation_inverse_evenement,
    transformer_evenement_lorentz,
    transformer_vitesse_lorentz,
)
from universe_sim.values import Vecteur3


class SpecialRelativityKinematicsTests(unittest.TestCase):
    def test_momentum_velocity_round_trip(self):
        mass = 1200.0
        velocity = Vecteur3(0.92 * C, 0.0, 0.0)
        momentum = impulsion_relativiste(mass, velocity)
        recovered = vitesse_depuis_impulsion(mass, momentum)
        self.assertLess(abs(recovered.x - velocity.x) / C, 1e-14)
        self.assertLess(recovered.norm(), C)

    def test_four_momentum_invariant_is_rest_mass(self):
        mass = 42.0
        q = quadrimpulsion_depuis_vitesse(mass, Vecteur3(0.8 * C, 0.1 * C, 0.0))
        self.assertAlmostEqual(q.invariant_masse2(), mass * mass, places=9)

    def test_lorentz_interval_is_invariant(self):
        origin = EvenementMinkowski(0.0, Vecteur3.zero())
        event = EvenementMinkowski(7.0, Vecteur3(0.2 * C * 7.0, 2.0e8, -1.0e8))
        before = event.intervalle_depuis(origin)
        boost = Vecteur3(0.65 * C, 0.0, 0.0)
        transformed = transformer_evenement_lorentz(event, boost)
        transformed_origin = transformer_evenement_lorentz(origin, boost)
        after = transformed.intervalle_depuis(transformed_origin)
        self.assertLess(abs(after - before) / abs(before), 1e-12)

    def test_lorentz_event_round_trip(self):
        event = EvenementMinkowski(3.25, Vecteur3(1.1e8, -2.0e8, 4.0e7))
        boost = Vecteur3(0.45 * C, 0.1 * C, 0.0)
        transformed = transformer_evenement_lorentz(event, boost)
        recovered = transformation_inverse_evenement(transformed, boost)
        self.assertLess(abs(recovered.t_s - event.t_s), 1e-12)
        self.assertLess((recovered.position_m - event.position_m).norm(), 1e-5)

    def test_light_speed_is_invariant_under_boost(self):
        transformed = transformer_vitesse_lorentz(Vecteur3(C, 0.0, 0.0), Vecteur3(0.8 * C, 0.0, 0.0))
        self.assertLess(abs(transformed.norm() - C) / C, 1e-12)

    def test_superluminal_input_is_rejected(self):
        with self.assertRaises(ValueError):
            facteur_lorentz(Vecteur3(C, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
