"""Coordinate-time orchestrator for coexisting physical dynamics regimes."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Protocol

from ..bodies import CorpsPhysique
from ..constants import C
from ..events import EvenementPhysique, TypeEvenement
from ..regimes import NiveauActiviteCalcul, RegimeDynamique
from ..relativistic_state import EtatCinematiqueRelativiste, TypeCourbeCausale
from ..services.horizons import detecter_franchissement_horizon
from ..systems import Univers
from ..values import Instant, Vecteur3
from .clock import HorlogeSimulation
from .configuration import ConfigurationPhysique
from .coordinate_time import IntegrateurAffine, avancer_jusqua_temps_coordonne
from .diagnostics import ControlePhysique
from .geodesic_integrator import EtatGeodesique, TypeGeodesique
from .snapshot import Snapshot
from .sr_integrator import EtatParticuleSR, IntegrateurRelativisteSpecial


class EvolutionRegime(Protocol):
    regime: RegimeDynamique

    @property
    def corps_ids(self) -> tuple[str, ...]: ...

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]: ...


ForceProviderSR = Callable[[CorpsPhysique, Univers, Instant], Vecteur3]


@dataclass(slots=True)
class EvolutionSRCorps:
    corps_id: str
    force_provider: ForceProviderSR = lambda _body, _universe, _instant: Vecteur3.zero()
    integrateur: IntegrateurRelativisteSpecial = field(default_factory=IntegrateurRelativisteSpecial)
    regime: RegimeDynamique = field(default=RegimeDynamique.RELATIVISTE_SPECIAL, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return (self.corps_id,)

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        body = univers.trouver_corps(self.corps_id)
        state = body.etat()
        if state.relativiste is None or state.massique is None or state.massique.masse.value <= 0:
            raise ValueError(f"{body.nom} requires relativistic kinematics and positive rest mass")
        rel = state.relativiste
        hot = EtatParticuleSR(rel.position, rel.impulsion, state.massique.masse.value, rel.temps_propre_s)
        force = self.force_provider(body, univers, instant)
        self.integrateur.avancer_force_constante(hot, force, dt_s)
        state.relativiste = EtatCinematiqueRelativiste(hot.position_m, hot.impulsion_kg_m_s, hot.temps_propre_s)
        state.instant = Instant(instant.seconds + dt_s)
        return []


@dataclass(slots=True)
class EvolutionGeodesiqueCorps:
    corps_id: str
    integrateur: IntegrateurAffine
    dlambda_max_m: float | None = None
    regime: RegimeDynamique = field(default=RegimeDynamique.GEODESIQUE, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return (self.corps_id,)

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        body = univers.trouver_corps(self.corps_id)
        state = body.etat()
        curved = state.espace_temps
        if curved is None:
            raise ValueError(f"{body.nom} requires curved-space-time kinematics")
        causal = TypeGeodesique.TEMPORELLE if curved.type_causal == TypeCourbeCausale.TEMPORELLE else TypeGeodesique.NULLE
        hot = EtatGeodesique(curved.coordonnees_m, curved.tangente, curved.parametre_affine_m, causal)
        before = hot.coordonnees_m
        dlambda = avancer_jusqua_temps_coordonne(
            self.integrateur,
            hot,
            dt_s,
            dlambda_max_m=self.dlambda_max_m,
        )
        curved.coordonnees_m = hot.coordonnees_m
        curved.tangente = hot.tangente
        curved.parametre_affine_m = hot.parametre_affine_m
        if curved.type_causal == TypeCourbeCausale.TEMPORELLE:
            assert curved.temps_propre_s is not None
            curved.temps_propre_s += dlambda / C
        state.instant = Instant(instant.seconds + dt_s)

        metric = getattr(self.integrateur, "metrique", None)
        if metric is None:
            return []
        try:
            crossing = detecter_franchissement_horizon(metric, before, hot.coordonnees_m)
        except TypeError:
            return []
        if crossing is None:
            return []
        p0 = Vecteur3(before[1], before[2], before[3])
        p1 = Vecteur3(hot.coordonnees_m[1], hot.coordonnees_m[2], hot.coordonnees_m[3])
        position = p0 + (p1 - p0) * crossing.fraction_pas
        event_time = Instant(instant.seconds + dt_s * crossing.fraction_pas)
        return [
            EvenementPhysique(
                TypeEvenement.FRANCHISSEMENT_HORIZON,
                event_time,
                (body.id,),
                position,
                {
                    "rayon_horizon_m": crossing.rayon_horizon_m,
                    "rayon_avant_m": crossing.rayon_avant_m,
                    "rayon_apres_m": crossing.rayon_apres_m,
                    "localisation": "interpolation_radiale_dans_le_pas",
                },
            )
        ]


@dataclass(slots=True)
class EvolutionClassiqueGroupe:
    """Advance a selected classical N-body subset through the existing engine."""

    corps_selectionnes: tuple[str, ...]
    moteur: object
    integrateur: object
    regime: RegimeDynamique = field(default=RegimeDynamique.CLASSIQUE, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return self.corps_selectionnes

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        bodies = [univers.trouver_corps(body_id) for body_id in self.corps_selectionnes]
        subset = Univers(
            nom=f"{univers.nom} [vue classique]",
            modele_espace_temps=univers.modele_espace_temps,
            corps_physiques=bodies,
            systemes_physiques=[],
            structures_observationnelles=univers.structures_observationnelles,
            champs=univers.champs,
            constantes_physiques=univers.constantes_physiques,
        )
        advance = getattr(self.integrateur, "avancer", None)
        if advance is None:
            raise TypeError("Classical integrator must expose avancer(univers,moteur,instant,dt)")
        advance(subset, self.moteur, instant, dt_s)
        return []


@dataclass(slots=True)
class SimulationMultiRegime:
    univers: Univers
    horloge: HorlogeSimulation
    configuration: ConfigurationPhysique
    evolutions: list[EvolutionRegime] = field(default_factory=list)
    historique_evenements: list[EvenementPhysique] = field(default_factory=list)
    snapshots: list[Snapshot] = field(default_factory=list)
    pas_effectues: int = 0
    exiger_couverture_complete: bool = True
    controle_classique: ControlePhysique = field(default_factory=ControlePhysique)
    _corps_enregistres: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        initial = list(self.evolutions)
        self.evolutions = []
        for evolution in initial:
            self.ajouter_evolution(evolution)

    def ajouter_evolution(self, evolution: EvolutionRegime) -> None:
        ids = tuple(evolution.corps_ids)
        if not ids:
            raise ValueError("A dynamics evolution must own at least one body")
        overlap = self._corps_enregistres.intersection(ids)
        if overlap:
            raise ValueError(f"Bodies already assigned to another dynamics evolution: {sorted(overlap)}")
        for body_id in ids:
            self.univers.trouver_corps(body_id)
            explicit = self.configuration.regimes_par_corps.get(body_id)
            if explicit is not None and explicit != evolution.regime:
                raise ValueError(f"Configured regime {explicit} conflicts with evolution regime {evolution.regime} for {body_id}")
        for body_id in ids:
            self.configuration.definir_regime(body_id, evolution.regime)
        self._corps_enregistres.update(ids)
        self.evolutions.append(evolution)

    def verifier_couverture(self) -> None:
        if not self.exiger_couverture_complete:
            return
        missing = [
            body.id
            for body in self.univers.corps_physiques
            if body.actif
            and self.configuration.niveau_activite_pour(body.id) == NiveauActiviteCalcul.ACTIVE
            and body.id not in self._corps_enregistres
        ]
        if missing:
            raise RuntimeError(f"Active bodies without a dynamics evolution: {missing}")

    def _enregistrer_snapshot_si_necessaire(self) -> None:
        if not self.configuration.conserver_historique:
            return
        cadence = max(1, self.configuration.enregistrer_tous_les_n_pas)
        if self.pas_effectues % cadence != 0:
            return
        self.snapshots.append(Snapshot.capturer(self.univers, self.horloge.instant_courant))
        for body in self.univers.corps_physiques:
            body.enregistrer_etat()

    def avancer(self, dt_s: float | None = None) -> list[EvenementPhysique]:
        step = self.horloge.pas_temps.seconds if dt_s is None else float(dt_s)
        if step <= 0:
            raise ValueError("Time step must be positive")
        self.verifier_couverture()
        instant = self.horloge.instant_courant
        backup = {body.id: body.etat().copier() for body in self.univers.corps_physiques}
        events: list[EvenementPhysique] = []
        try:
            for evolution in self.evolutions:
                events.extend(evolution.avancer(self.univers, instant, step))
        except Exception:
            for body in self.univers.corps_physiques:
                body.etat_courant = backup[body.id]
            raise
        self.horloge.avancer(step)
        self.pas_effectues += 1
        self.historique_evenements.extend(events)
        self._enregistrer_snapshot_si_necessaire()
        return events

    def executer(self, duree_s: float, dt_s: float | None = None) -> None:
        if duree_s < 0:
            raise ValueError("Duration must be non-negative")
        step = self.horloge.pas_temps.seconds if dt_s is None else float(dt_s)
        target = self.horloge.instant_courant.seconds + duree_s
        while self.horloge.instant_courant.seconds < target - 1e-12:
            self.avancer(min(step, target - self.horloge.instant_courant.seconds))

    def diagnostic(self) -> dict[str, object]:
        active = [body for body in self.univers.corps_physiques if body.actif]
        regimes = Counter(self.configuration.regime_pour(body.id).value for body in active)
        all_classical = all(
            self.configuration.regime_pour(body.id) == RegimeDynamique.CLASSIQUE
            for body in active
        )
        if all_classical:
            result = dict(self.controle_classique.mesurer(self.univers))
        else:
            result = {
                "energie_mecanique": None,
                "derive_relative_energie": None,
                "quantite_mouvement": None,
                "moment_cinetique": None,
            }

        gammas: list[float] = []
        proper_times: list[float] = []
        for body in active:
            state = body.etat()
            if state.relativiste is not None and state.massique is not None and state.massique.masse.value > 0:
                gammas.append(state.relativiste.gamma(state.massique.masse.value))
                proper_times.append(state.relativiste.temps_propre_s)
            if state.espace_temps is not None and state.espace_temps.temps_propre_s is not None:
                proper_times.append(state.espace_temps.temps_propre_s)

        result.update(
            {
                "regimes": dict(sorted(regimes.items())),
                "gamma_max_sr": max(gammas) if gammas else None,
                "temps_propre_min_s": min(proper_times) if proper_times else None,
                "temps_propre_max_s": max(proper_times) if proper_times else None,
                "note_energie": (
                    "Newtonian mechanical energy is reported only for an entirely classical run; "
                    "no generic global mechanical energy is asserted for mixed/curved space-time runs."
                ),
            }
        )
        return result
