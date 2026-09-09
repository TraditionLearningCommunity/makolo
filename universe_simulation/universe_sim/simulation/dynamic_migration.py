"""Explicit migration between hot SR populations and materialized GR worldlines."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..events import EvenementPhysique, EvenementSimulation, TypeEvenementSimulation
from ..metrics import Metrique4D
from ..regimes import RegimeDynamique
from ..services.regime_transitions import vers_espace_temps_courbe
from ..states import EtatPhysique
from ..systems import Univers
from ..values import Instant
from .array_backend import ArrayStateBackend, _REGIME_TO_CODE
from .large_scale_engine import DomainePopulationSR
from .multiregime import EvolutionGeodesiqueCorps


@dataclass(slots=True)
class DomaineObjetsRelativistesGeneraux:
    """Small materialized GR set evolving beside large array populations."""

    nom: str
    univers: Univers
    evolutions: dict[str, EvolutionGeodesiqueCorps] = field(default_factory=dict)
    regime: RegimeDynamique = field(default=RegimeDynamique.RELATIVISTE_GENERAL, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return tuple(self.evolutions)

    @property
    def corps_participants(self) -> tuple[str, ...]:
        return self.corps_ids

    def ajouter_evolution(self, evolution: EvolutionGeodesiqueCorps) -> None:
        if evolution.regime != RegimeDynamique.RELATIVISTE_GENERAL:
            raise ValueError("GR object domain accepts only general-relativistic evolutions")
        if evolution.corps_id in self.evolutions:
            raise ValueError(f"Body {evolution.corps_id} is already materialized in GR domain {self.nom}")
        self.univers.trouver_corps(evolution.corps_id)
        self.evolutions[evolution.corps_id] = evolution

    def retirer_evolution(self, body_id: str) -> EvolutionGeodesiqueCorps:
        try:
            return self.evolutions.pop(body_id)
        except KeyError as exc:
            raise KeyError(f"Body {body_id} is not materialized in GR domain {self.nom}") from exc

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        events: list[EvenementPhysique] = []
        for evolution in tuple(self.evolutions.values()):
            events.extend(evolution.avancer(self.univers, instant, dt_s))
        return events

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None:
        if univers.id != self.univers.id:
            raise ValueError("GR object domain is bound to a different universe")
        for body_id in self.corps_ids:
            state = univers.trouver_corps(body_id).etat()
            if abs(state.instant.seconds - instant.seconds) > max(1e-9, abs(instant.seconds) * 1e-12):
                raise RuntimeError(f"GR body {body_id} is not synchronized to the requested barrier")


@dataclass(slots=True)
class GestionnaireMigrationRegime:
    """Transactional numerical-ownership transfer between SR arrays and GR.

    SR -> GR can construct the curved representation because the scenario
    supplies an explicit metric/chart. GR -> SR deliberately requires an
    already constructed SR state from an explicit local observer/tetrad; the
    manager never invents that observer.
    """

    historique: list[EvenementSimulation] = field(default_factory=list)

    @staticmethod
    def _verifier_integrateur_metrique(evolution: EvolutionGeodesiqueCorps, metrique: Metrique4D) -> None:
        integrator_metric = getattr(evolution.integrateur, "metrique", None)
        if integrator_metric is not metrique:
            raise ValueError("GR evolution integrator must use the exact metric supplied for state conversion")

    @staticmethod
    def _snapshot_ligne(backend: ArrayStateBackend, index: int) -> dict[str, object]:
        assert backend.participating is not None
        return {
            "position": backend.positions_m[index].copy(),
            "velocity": backend.velocities_m_s[index].copy(),
            "momentum": backend.momenta_kg_m_s[index].copy(),
            "mass": float(backend.masses_kg[index]),
            "charge": float(backend.charges_c[index]),
            "proper_time": float(backend.proper_times_s[index]),
            "active": bool(backend.active[index]),
            "regime": int(backend.regime_codes[index]),
            "participating": bool(backend.participating[index]),
        }

    @staticmethod
    def _restaurer_ligne(backend: ArrayStateBackend, index: int, snapshot: dict[str, object]) -> None:
        assert backend.participating is not None
        backend.positions_m[index] = snapshot["position"]
        backend.velocities_m_s[index] = snapshot["velocity"]
        backend.momenta_kg_m_s[index] = snapshot["momentum"]
        backend.masses_kg[index] = snapshot["mass"]
        backend.charges_c[index] = snapshot["charge"]
        backend.proper_times_s[index] = snapshot["proper_time"]
        backend.active[index] = snapshot["active"]
        backend.regime_codes[index] = snapshot["regime"]
        backend.participating[index] = snapshot["participating"]

    @staticmethod
    def _charger_sr_depuis_etat(backend: ArrayStateBackend, body: object) -> None:
        state = body.etat()
        if state.relativiste is None or state.translation is not None or state.espace_temps is not None:
            raise ValueError("Return to SR requires an explicit flat-space relativistic state")
        if state.massique is None or state.massique.masse.value <= 0:
            raise ValueError("Return to SR requires positive rest mass")
        index = backend.index(body.id)
        rel = state.relativiste
        backend.positions_m[index] = np.asarray(rel.position.as_tuple(), dtype=np.float64)
        backend.momenta_kg_m_s[index] = np.asarray(rel.impulsion.as_tuple(), dtype=np.float64)
        backend.masses_kg[index] = state.massique.masse.value
        backend.charges_c[index] = 0.0 if state.electrique is None else state.electrique.charge_nette.value
        backend.proper_times_s[index] = rel.temps_propre_s
        backend.active[index] = bool(body.actif)
        backend.regime_codes[index] = _REGIME_TO_CODE[RegimeDynamique.RELATIVISTE_SPECIAL]
        backend.rafraichir_vitesses()

    def materialiser_sr_vers_gr(
        self,
        univers: Univers,
        source: DomainePopulationSR,
        cible: DomaineObjetsRelativistesGeneraux,
        body_id: str,
        metrique: Metrique4D,
        evolution_gr: EvolutionGeodesiqueCorps,
        instant: Instant,
    ) -> tuple[EvenementSimulation, EvenementSimulation]:
        if evolution_gr.corps_id != body_id:
            raise ValueError("GR evolution body id does not match migration body id")
        self._verifier_integrateur_metrique(evolution_gr, metrique)
        index = source.backend.index(body_id)
        assert source.backend.participating is not None
        if not source.backend.active[index]:
            raise ValueError("A physically inactive body cannot be materialized into GR")
        if not source.backend.participating[index]:
            raise ValueError("Body is not currently owned by the source SR backend")
        if source.backend.regime(body_id) != RegimeDynamique.RELATIVISTE_SPECIAL:
            raise ValueError("Source row is not special-relativistic")

        body = univers.trouver_corps(body_id)
        old_state = body.etat().copier()
        line_snapshot = self._snapshot_ligne(source.backend, index)
        source.backend.synchroniser_un_corps(body)
        converted = vers_espace_temps_courbe(
            body.etat(), metrique, temps_coordonne_s=instant.seconds
        )
        converted.instant = instant

        try:
            source.backend.suspendre_calcul(body_id)
            body.etat_courant = converted
            cible.ajouter_evolution(evolution_gr)
        except Exception:
            body.etat_courant = old_state
            self._restaurer_ligne(source.backend, index, line_snapshot)
            raise

        metric_name = type(metrique).__name__
        change = EvenementSimulation(
            TypeEvenementSimulation.CHANGEMENT_REGIME_DYNAMIQUE,
            instant,
            body_id,
            {"from": "relativiste_special", "to": "relativiste_general", "metric": metric_name},
        )
        materialization = EvenementSimulation(
            TypeEvenementSimulation.MATERIALISATION_LOD,
            instant,
            body_id,
            {"source_domain": source.nom, "target_domain": cible.nom, "reason": "curved_spacetime_required"},
        )
        self.historique.extend((change, materialization))
        return change, materialization

    def dematerialiser_gr_vers_sr(
        self,
        univers: Univers,
        source_gr: DomaineObjetsRelativistesGeneraux,
        cible_sr: DomainePopulationSR,
        body_id: str,
        etat_sr_explicite: EtatPhysique,
        instant: Instant,
    ) -> tuple[EvenementSimulation, EvenementSimulation]:
        """Return to SR using a state explicitly projected by the caller.

        The caller must choose the local observer/tetrad used to construct
        ``etat_sr_explicite``. Coordinate GR velocity is never silently treated
        as an inertial SR velocity by this method.
        """
        if body_id not in source_gr.evolutions:
            raise ValueError("Body is not currently owned by the GR object domain")
        if etat_sr_explicite.relativiste is None or etat_sr_explicite.espace_temps is not None:
            raise ValueError("Explicit return state must use special-relativistic kinematics")
        index = cible_sr.backend.index(body_id)
        assert cible_sr.backend.participating is not None
        if cible_sr.backend.participating[index]:
            raise ValueError("Target SR row is already participating")

        body = univers.trouver_corps(body_id)
        old_state = body.etat().copier()
        line_snapshot = self._snapshot_ligne(cible_sr.backend, index)
        old_evolution = source_gr.evolutions[body_id]
        new_state = etat_sr_explicite.copier()
        new_state.instant = instant

        try:
            source_gr.retirer_evolution(body_id)
            body.etat_courant = new_state
            self._charger_sr_depuis_etat(cible_sr.backend, body)
            cible_sr.backend.reprendre_calcul(body_id)
        except Exception:
            body.etat_courant = old_state
            self._restaurer_ligne(cible_sr.backend, index, line_snapshot)
            source_gr.evolutions[body_id] = old_evolution
            raise

        change = EvenementSimulation(
            TypeEvenementSimulation.CHANGEMENT_REGIME_DYNAMIQUE,
            instant,
            body_id,
            {"from": "relativiste_general", "to": "relativiste_special", "projection": "explicit_local_observer"},
        )
        dematerialization = EvenementSimulation(
            TypeEvenementSimulation.DEMATERIALISATION_LOD,
            instant,
            body_id,
            {"source_domain": source_gr.nom, "target_domain": cible_sr.nom, "reason": "curvature_below_selected_tolerance"},
        )
        self.historique.extend((change, dematerialization))
        return change, dematerialization
