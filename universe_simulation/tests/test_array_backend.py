import math
from types import SimpleNamespace
import numpy as np
from universe_sim.constants import C
from universe_sim.values import GrandeurPhysique, Vecteur3
from universe_sim.simulation.array_backend import ArrayStateBackend

class Body:
    def __init__(self, body_id, name, state): self.id=body_id; self.nom=name; self._s=state; self.actif=True
    def etat(self): return self._s

def mass(m): return SimpleNamespace(masse=GrandeurPhysique(m,'kg'))
def charge(q=0): return SimpleNamespace(charge_nette=GrandeurPhysique(q,'C'))

def test_classical_and_sr_roundtrip():
    classical = SimpleNamespace(
        translation=SimpleNamespace(position=Vecteur3(1,2,3),vitesse=Vecteur3(4,5,6)),
        relativiste=None, espace_temps=None, massique=mass(2), electrique=charge(3)
    )
    gamma=1/math.sqrt(1-.8**2); p=gamma*5*.8*C
    sr = SimpleNamespace(
        translation=None,
        relativiste=SimpleNamespace(position=Vecteur3(7,8,9), impulsion=Vecteur3(p,0,0), temps_propre_s=11.),
        espace_temps=None, massique=mass(5), electrique=charge()
    )
    b1,b2=Body('a','A',classical),Body('b','B',sr)
    backend=ArrayStateBackend.depuis_corps([b1,b2])
    assert backend.positions_m.shape==(2,3)
    assert abs(backend.velocities_m_s[1,0]/C-.8)<1e-12
    backend.positions_m[0,0]=10
    backend.momenta_kg_m_s[1,0]*=1.1
    backend.proper_times_s[1]=12
    backend.synchroniser_vers_corps([b1,b2])
    assert b1.etat().translation.position.x==10
    assert b2.etat().relativiste.temps_propre_s==12
    assert b2.etat().relativiste.position.x==7
    assert np.linalg.norm(backend.velocities_m_s[1]) < C

def test_curved_state_is_rejected():
    state=SimpleNamespace(translation=None,relativiste=None,espace_temps=object(),massique=mass(1),electrique=None)
    try:
        ArrayStateBackend.depuis_corps([Body('g','GR',state)])
    except ValueError as exc:
        assert 'curved-space-time' in str(exc)
    else:
        raise AssertionError('expected curved state rejection')


def test_extreme_sr_momentum_remains_representably_subluminal():
    backend = ArrayStateBackend(
        ("sr",),
        np.zeros((1, 3)),
        np.zeros((1, 3)),
        np.array([[1e40, -2e40, 3e40]], dtype=float),
        np.array([1.0]),
        np.zeros(1),
        np.zeros(1),
        np.ones(1, dtype=bool),
        np.ones(1, dtype=np.int8),
    )
    original = backend.momenta_kg_m_s.copy()
    backend.rafraichir_vitesses()
    speed = np.linalg.norm(backend.velocities_m_s[0])
    assert np.isfinite(speed)
    assert speed < C
    assert np.array_equal(backend.momenta_kg_m_s, original)
