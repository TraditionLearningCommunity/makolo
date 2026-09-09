"""Ideal collinear relativistic rocket propagation in flat space-time.

The model follows the Ackeret relativistic rocket relation for a prescribed
constant effective exhaust speed in the instantaneous rocket frame. It is a
well-defined special case, not a generic model of arbitrary relativistic
propulsion or exhaust thermodynamics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import atanh, cosh, log, sinh, tanh
from typing import Callable

from ..bodies import CorpsPhysique
from ..constants import C
from ..events import EvenementPhysique, TypeEvenement
from ..regimes import RegimeDynamique
from ..relativistic_state import EtatCinematiqueRelativiste
from ..relativistic_values import impulsion_relativiste
from ..systems import Univers
from ..values import GrandeurPhysique, Instant, Vecteur3
from .sr_integrator import EtatParticuleSR


@dataclass(frozen=True, slots=True)
class ParametresFuseeRelativisteIdeale:
    vitesse_ejection_m_s: float
    debit_masse_propre_kg_s: float
    masse_seche_kg: float

    def __post_init__(self) -> None:
        if not 0.0 < self.vitesse_ejection_m_s < C:
            raise ValueError("Effective exhaust speed must satisfy 0 < ve < c")
        if self.debit_masse_propre_kg_s < 0:
            raise ValueError("Proper mass-flow rate cannot be negative")
        if self.masse_seche_kg <= 0:
            raise ValueError("Dry mass must be positive")

    @property
    def rapport_ejection(self) -> float:
        return self.vitesse_ejection_m_s / C


@dataclass(frozen=True, slots=True)
class ResultatPousseeRelativiste:
    masse_consommee_kg: float
    temps_coordonne_epuisement_s: float | None = None
    deplacement_epuisement_m: float | None = None
    temps_propre_ecoule_s: float = 0.0


@dataclass(slots=True)
class IntegrateurFuseeRelativisteIdeale:
    parametres: ParametresFuseeRelativisteIdeale
    dtau_max_s: float = 3600.0
    tolerance_colinearite: float = 1e-10
    nom: str = "Fusee relativiste ideale Ackeret"

    def __post_init__(self) -> None:
        if self.dtau_max_s <= 0:
            raise ValueError("Maximum proper-time substep must be positive")

    def _rapidite_initiale(self, etat: EtatParticuleSR, axis: Vecteur3) -> float:
        velocity = etat.vitesse_m_s
        parallel = velocity.dot(axis)
        perpendicular = velocity - axis * parallel
        if perpendicular.norm() > self.tolerance_colinearite * C:
            raise ValueError("Ideal Ackeret propagator requires velocity collinear with thrust axis")
        beta = parallel / C
        if abs(beta) >= 1:
            raise ValueError("Massive rocket velocity must remain below c")
        return atanh(beta)

    def _step_proper(
        self,
        mass: float,
        eta: float,
        dtau: float,
        thrust_sign: float,
    ) -> tuple[float, float, float, float]:
        """RK4 proper-time step returning mass, rapidity, dt and dx."""
        q = self.parametres.debit_masse_propre_kg_s
        dry = self.parametres.masse_seche_kg
        k = self.parametres.rapport_ejection * thrust_sign

        def derivative(m: float, e: float) -> tuple[float, float, float, float]:
            burning = q > 0.0 and m > dry
            dm = -q if burning else 0.0
            deta = (k * q / m) if burning else 0.0
            return dm, deta, cosh(e), C * sinh(e)

        k1 = derivative(mass, eta)
        k2 = derivative(mass + 0.5 * dtau * k1[0], eta + 0.5 * dtau * k1[1])
        k3 = derivative(mass + 0.5 * dtau * k2[0], eta + 0.5 * dtau * k2[1])
        k4 = derivative(mass + dtau * k3[0], eta + dtau * k3[1])
        mass1 = mass + dtau * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]) / 6.0
        eta1 = eta + dtau * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]) / 6.0
        dt = dtau * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2]) / 6.0
        dx = dtau * (k1[3] + 2.0 * k2[3] + 2.0 * k3[3] + k4[3]) / 6.0
        if mass1 < dry and dry - mass1 < 1e-9 * max(1.0, dry):
            mass1 = dry
        return mass1, eta1, dt, dx

    def avancer_temps_coordonne(
        self,
        etat: EtatParticuleSR,
        dt_coordonne_s: float,
        direction: Vecteur3,
        signe_poussee: float = 1.0,
    ) -> ResultatPousseeRelativiste:
        """Advance to an exact coordinate-time target and report fuel use."""
        if dt_coordonne_s <= 0:
            raise ValueError("Coordinate-time step must be positive")
        if signe_poussee == 0:
            raise ValueError("Thrust sign must be non-zero; use zero mass flow to model engine-off coasting")
        axis = direction.normalized()
        eta = self._rapidite_initiale(etat, axis)
        mass0 = etat.masse_repos_kg
        mass = mass0
        dry = self.parametres.masse_seche_kg
        q = self.parametres.debit_masse_propre_kg_s
        if mass < dry:
            raise ValueError("Rocket rest mass cannot be below dry mass")

        elapsed_t = 0.0
        elapsed_tau = 0.0
        dx_total = 0.0
        exhaustion_time: float | None = None
        exhaustion_dx: float | None = None
        tolerance_t = max(1e-12, 1e-13 * dt_coordonne_s)

        while elapsed_t < dt_coordonne_s - tolerance_t:
            remaining_t = dt_coordonne_s - elapsed_t
            if q <= 0.0 or mass <= dry * (1.0 + 1e-15):
                gamma = cosh(eta)
                dtau = remaining_t / gamma
                elapsed_tau += dtau
                dx_total += C * tanh(eta) * remaining_t
                elapsed_t = dt_coordonne_s
                break

            fuel_tau = (mass - dry) / q
            trial_tau = min(self.dtau_max_s, fuel_tau, remaining_t / cosh(eta))
            if trial_tau <= 0:
                mass = max(dry, mass)
                continue
            mass_before_step = mass
            candidate = self._step_proper(mass, eta, trial_tau, signe_poussee)
            if elapsed_t + candidate[2] > dt_coordonne_s + tolerance_t:
                low = 0.0
                high = trial_tau
                for _ in range(60):
                    mid = 0.5 * (low + high)
                    trial = self._step_proper(mass, eta, mid, signe_poussee)
                    if elapsed_t + trial[2] < dt_coordonne_s:
                        low = mid
                    else:
                        high = mid
                trial_tau = high
                candidate = self._step_proper(mass, eta, trial_tau, signe_poussee)
            mass, eta, dt_step, dx_step = candidate
            mass = max(dry, mass)
            elapsed_t += dt_step
            elapsed_tau += trial_tau
            dx_total += dx_step
            if exhaustion_time is None and mass_before_step > dry and mass <= dry * (1.0 + 1e-12):
                exhaustion_time = min(elapsed_t, dt_coordonne_s)
                exhaustion_dx = dx_total

        etat.position_m = etat.position_m + axis * dx_total
        etat.masse_repos_kg = mass
        etat.temps_propre_s += elapsed_tau
        velocity = axis * (C * tanh(eta))
        etat.impulsion_kg_m_s = impulsion_relativiste(mass, velocity)
        return ResultatPousseeRelativiste(mass0 - mass, exhaustion_time, exhaustion_dx, elapsed_tau)

    def rapidite_ackeret(self, masse_initiale_kg: float, masse_finale_kg: float, signe_poussee: float = 1.0) -> float:
        if masse_initiale_kg <= 0 or masse_finale_kg <= 0 or masse_finale_kg > masse_initiale_kg:
            raise ValueError("Ackeret mass ratio requires 0 < mf <= mi")
        return signe_poussee * self.parametres.rapport_ejection * log(masse_initiale_kg / masse_finale_kg)


DirectionProvider = Callable[[CorpsPhysique, Univers, Instant], Vecteur3]
SignePousseeProvider = Callable[[CorpsPhysique, Univers, Instant], float]


@dataclass(slots=True)
class EvolutionFuseeRelativisteIdeale:
    corps_id: str
    integrateur: IntegrateurFuseeRelativisteIdeale
    direction_provider: DirectionProvider = lambda _body, _universe, _instant: Vecteur3(1.0, 0.0, 0.0)
    signe_poussee_provider: SignePousseeProvider = lambda _body, _universe, _instant: 1.0
    regime: RegimeDynamique = field(default=RegimeDynamique.RELATIVISTE_SPECIAL, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return (self.corps_id,)

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        body = univers.trouver_corps(self.corps_id)
        state = body.etat()
        if state.relativiste is None or state.massique is None or state.massique.masse.value <= 0:
            raise ValueError(f"{body.nom} requires SR kinematics and positive rest mass")
        rel = state.relativiste
        hot = EtatParticuleSR(rel.position, rel.impulsion, state.massique.masse.value, rel.temps_propre_s)
        before_mass = hot.masse_repos_kg
        direction = self.direction_provider(body, univers, instant)
        sign = self.signe_poussee_provider(body, univers, instant)
        start_position = rel.position
        result = self.integrateur.avancer_temps_coordonne(hot, dt_s, direction, sign)
        consumed = result.masse_consommee_kg
        state.relativiste = EtatCinematiqueRelativiste(hot.position_m, hot.impulsion_kg_m_s, hot.temps_propre_s)
        old_mass_quantity = state.massique.masse
        state.massique.masse = GrandeurPhysique(
            hot.masse_repos_kg,
            old_mass_quantity.unit,
            old_mass_quantity.uncertainty,
        )
        propellant = getattr(body, "masse_propergol", None)
        if propellant is not None:
            remaining = max(0.0, propellant.value - consumed)
            body.masse_propergol = GrandeurPhysique(remaining, propellant.unit, propellant.uncertainty)
        state.instant = Instant(instant.seconds + dt_s)

        dry = self.integrateur.parametres.masse_seche_kg
        if before_mass > dry and hot.masse_repos_kg <= dry * (1.0 + 1e-12):
            offset = dt_s if result.temps_coordonne_epuisement_s is None else result.temps_coordonne_epuisement_s
            event_position = state.relativiste.position
            if result.deplacement_epuisement_m is not None:
                event_position = start_position + direction.normalized() * result.deplacement_epuisement_m
            return [
                EvenementPhysique(
                    TypeEvenement.EPUISEMENT_PROPERGOL,
                    Instant(instant.seconds + offset),
                    (body.id,),
                    event_position,
                    {"masse_seche_kg": dry, "masse_consommee_kg": consumed},
                )
            ]
        return []
