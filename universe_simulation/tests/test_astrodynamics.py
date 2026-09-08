import unittest
from math import sqrt
from universe_sim.constants import AU,G,SOLAR_MASS
from universe_sim.services.astrodynamics import elements_orbitaux_vers_etat,etat_vers_elements_orbitaux,periode_orbitale,sphere_hill
from universe_sim.values import Instant,Vecteur3
class AstrodynamicsTests(unittest.TestCase):
 def test_circular_orbit_elements(self):
  mu=G*SOLAR_MASS;r=Vecteur3(AU,0,0);v=Vecteur3(0,sqrt(mu/AU),0);el=etat_vers_elements_orbitaux(r,v,mu,Instant(0));self.assertAlmostEqual(el.demi_grand_axe/AU,1,places=10);self.assertLess(el.excentricite,1e-10);r2,v2=elements_orbitaux_vers_etat(el,mu);self.assertLess((r2-r).norm()/AU,1e-10);self.assertLess((v2-v).norm()/v.norm(),1e-10)
 def test_orbital_period_is_one_year_like(self):self.assertTrue(365<periode_orbitale(AU,G*SOLAR_MASS)/86400<366)
 def test_hill_radius_positive(self):self.assertGreater(sphere_hill(AU,.0167,5.9722e24,SOLAR_MASS),1e9)
