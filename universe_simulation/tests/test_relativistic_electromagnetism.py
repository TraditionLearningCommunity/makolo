import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.fields import ChampElectrique, ChampElectromagnetique, ChampMagnetique
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.services.relativistic_electromagnetism import creer_force_provider_lorentz_sr, force_lorentz_sr
from universe_sim.simulation.multiregime import EvolutionSRCorps
from universe_sim.states import EtatElectrique, EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


class RelativisticElectromagnetismTests(unittest.TestCase):
    def test_magnetic_part_does_no_instantaneous_work(self):
        velocity = Vecteur3(1.0e7, 2.0e7, -3.0e6)
        magnetic = Vecteur3(0.0, 0.0, 2.0)
        force = force_lorentz_sr(3.0, velocity, Vecteur3.zero(), magnetic)
        self.assertLess(abs(force.dot(velocity)), 1e-6 * max(1.0, force.norm() * velocity.norm()))

    def test_uniform_electric_field_updates_relativistic_momentum_not_velocity_directly(self):
        electric = ChampElectrique("E", lambda _p, _t: Vecteur3(3.0, 0.0, 0.0))
        magnetic = ChampMagnetique("B", lambda _p, _t: Vecteur3.zero())
        field = ChampElectromagnetique(electric, magnetic)
        body = CorpsPhysique(
            "charged",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1.0, "kg")),
                electrique=EtatElectrique(GrandeurPhysique(2.0, "C")),
                relativiste=EtatCinematiqueRelativiste(),
            ),
        )
        universe = Univers("em", corps_physiques=[body])
        evolution = EvolutionSRCorps(body.id, creer_force_provider_lorentz_sr(field))
        evolution.avancer(universe, Instant(0.0), 5.0)
        self.assertAlmostEqual(body.etat().relativiste.impulsion.x, 30.0, places=12)
        self.assertLess(body.etat().vitesse().norm(), 299_792_458.0)


if __name__ == "__main__":
    unittest.main()
