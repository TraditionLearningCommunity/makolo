from types import SimpleNamespace

from universe_sim.regimes import NiveauActiviteCalcul
from universe_sim.simulation.hierarchy import RegistreHierarchiqueUnivers
from universe_sim.values import GrandeurPhysique, Vecteur3


class _State:
    def __init__(self, position, velocity, frame="f"):
        self._position = position
        self._velocity = velocity
        self.espace_temps = None
        self.referentiel = SimpleNamespace(id=frame)
        self.systeme_coordonnees = SimpleNamespace(nom="cart")

    def position(self):
        return self._position

    def vitesse(self):
        return self._velocity


class _Body:
    def __init__(self, body_id, mass, position, velocity, radius=0):
        self.id = body_id
        self.nom = body_id
        self._mass = GrandeurPhysique(mass, "kg")
        self._state = _State(position, velocity)
        self.rayon_reference = GrandeurPhysique(radius, "m")

    def etat(self):
        return self._state

    def masse(self):
        return self._mass


class _System:
    def __init__(self, system_id, members=(), subs=()):
        self.id = system_id
        self.nom = system_id
        self.membres = list(members)
        self.sous_systemes = list(subs)


def test_nested_aggregate_deduplicates_bodies_and_computes_barycenter():
    a = _Body("a", 2, Vecteur3(0, 0, 0), Vecteur3(1, 0, 0), 1)
    b = _Body("b", 1, Vecteur3(9, 0, 0), Vecteur3(-2, 0, 0), 2)
    child = _System("child", [b])
    root = _System("root", [a], [child])
    registry = RegistreHierarchiqueUnivers(SimpleNamespace(systemes_physiques=[root, child]))
    state = registry.etat("root")
    assert state.masse_kg == 3
    assert abs(state.barycentre_m.x - 3) < 1e-12
    assert abs(state.vitesse_barycentrique_m_s.x) < 1e-12
    assert state.corps_ids == ("a", "b")
    assert state.rayon_couverture_m >= 8
    assert abs(sum(state.quadrupole_kg_m2[i][i] for i in range(3))) < 1e-8


def test_level_is_computational_and_survives_recalculation():
    a = _Body("a", 1, Vecteur3(), Vecteur3())
    root = _System("root", [a])
    registry = RegistreHierarchiqueUnivers(SimpleNamespace(systemes_physiques=[root]))
    registry.definir_niveau("root", NiveauActiviteCalcul.ACTIVE)
    registry.recalculer()
    assert registry.etat("root").niveau_activite == NiveauActiviteCalcul.ACTIVE


def test_multiple_system_parents_are_rejected():
    child = _System("child", [_Body("a", 1, Vecteur3(), Vecteur3())])
    r1 = _System("r1", subs=[child])
    r2 = _System("r2", subs=[child])
    try:
        RegistreHierarchiqueUnivers(SimpleNamespace(systemes_physiques=[r1, r2, child]))
    except ValueError as exc:
        assert "multiple" in str(exc)
    else:
        raise AssertionError("expected multiple-parent rejection")
