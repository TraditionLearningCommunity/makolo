import unittest
from math import pi
from universe_sim.examples import construire_systeme_solaire_minimal
from universe_sim.observation import Constellation,Observateur,RegionCeleste
from universe_sim.services.observation import determiner_constellation,effectuer_observation
from universe_sim.spacetime import REFERENTIEL_INERTIEL
from universe_sim.values import Instant
class ObservationTests(unittest.TestCase):
 def test_constellation_is_observational_not_membership(self):
  sim=construire_systeme_solaire_minimal();earth=sim.univers.trouver_corps("Terre");sun=sim.univers.trouver_corps("Soleil");observer=Observateur("Test",earth.etat().translation.position,REFERENTIEL_INERTIEL);obs=effectuer_observation(observer,sun,Instant(0),False);c=Constellation("Test constellation",region=RegionCeleste(0,2*pi,-pi/2,pi/2,"whole sky"));self.assertIs(determiner_constellation(obs,[c]),c);self.assertFalse(hasattr(c,"membres_physiques"))
