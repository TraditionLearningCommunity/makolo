import unittest
from universe_sim.constants import AU,DAY
from universe_sim.examples import construire_systeme_solaire_minimal
from universe_sim.laws.gravity import GravitationNewtonienne
from universe_sim.services.mechanics import calculer_barycentre
from universe_sim.values import Instant
class CorePhysicsTests(unittest.TestCase):
 def test_newton_action_reaction(self):
  sim=construire_systeme_solaire_minimal();a=sim.univers.trouver_corps("Soleil");b=sim.univers.trouver_corps("Terre");fa,fb=GravitationNewtonienne().force_entre(a,b,Instant(0));self.assertLess((fa.vecteur+fb.vecteur).norm(),max(1.,fa.vecteur.norm())*1e-14)
 def test_system_barycenter_is_finite(self):
  sim=construire_systeme_solaire_minimal();b=calculer_barycentre(sim.univers.systemes_physiques[0]);self.assertTrue(abs(b.x)<AU and abs(b.y)<AU)
 def test_one_day_simulation_stays_near_one_au(self):
  sim=construire_systeme_solaire_minimal(dt=3600);sim.executer(DAY);e=sim.univers.trouver_corps("Terre");s=sim.univers.trouver_corps("Soleil");d=e.etat().translation.position.distance_to(s.etat().translation.position);self.assertLess(abs(d-AU)/AU,5e-4)
 def test_energy_drift_is_small_for_rk4(self):
  sim=construire_systeme_solaire_minimal(dt=7200);initial=sim.diagnostic()["energie_mecanique"];sim.executer(30*DAY);final=sim.diagnostic()["energie_mecanique"];self.assertLess(abs((final-initial)/initial),1e-7)
