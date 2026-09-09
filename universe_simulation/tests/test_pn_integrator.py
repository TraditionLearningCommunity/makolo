import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import AU, EARTH_MASS, G, SOLAR_MASS
from universe_sim.simulation.pn_integrator import IntegrateurDeuxCorps1PNRK4
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


class PNIntegratorTests(unittest.TestCase):
    def make_pair(self):
        total = SOLAR_MASS + EARTH_MASS
        radius = AU
        omega = (G * total / radius**3) ** 0.5
        r1 = radius * EARTH_MASS / total
        r2 = radius * SOLAR_MASS / total
        sun = CorpsPhysique(
            "sun",
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(Vecteur3(-r1, 0.0, 0.0), Vecteur3(0.0, -omega * r1, 0.0)),
                massique=EtatMassique(GrandeurPhysique(SOLAR_MASS, "kg")),
            ),
        )
        earth = CorpsPhysique(
            "earth",
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(Vecteur3(r2, 0.0, 0.0), Vecteur3(0.0, omega * r2, 0.0)),
                massique=EtatMassique(GrandeurPhysique(EARTH_MASS, "kg")),
            ),
        )
        return sun, earth

    def test_barycenter_and_total_momentum_remain_near_zero(self):
        body1, body2 = self.make_pair()
        integrator = IntegrateurDeuxCorps1PNRK4()
        for index in range(100):
            integrator.avancer(body1, body2, Instant(index * 3600.0), 3600.0)
        m1, m2 = body1.masse().value, body2.masse().value
        com = (body1.etat().translation.position * m1 + body2.etat().translation.position * m2) / (m1 + m2)
        momentum = body1.etat().translation.vitesse * m1 + body2.etat().translation.vitesse * m2
        self.assertLess(com.norm(), 1e-2)
        self.assertLess(momentum.norm(), 1e17)

    def test_orbit_stays_close_to_one_au_over_one_day(self):
        body1, body2 = self.make_pair()
        integrator = IntegrateurDeuxCorps1PNRK4()
        for index in range(24):
            integrator.avancer(body1, body2, Instant(index * 3600.0), 3600.0)
        distance = body1.etat().translation.position.distance_to(body2.etat().translation.position)
        self.assertLess(abs(distance - AU) / AU, 1e-6)


if __name__ == "__main__":
    unittest.main()
