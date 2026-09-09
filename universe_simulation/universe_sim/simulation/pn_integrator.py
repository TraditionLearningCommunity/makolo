"""First post-Newtonian two-body integration in barycentric coordinates."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..bodies import CorpsPhysique
from ..events import EvenementPhysique
from ..regimes import RegimeDynamique
from ..services.post_newtonian import acceleration_relative_1pn, repartir_acceleration_relative
from ..states import EtatTranslationnel
from ..systems import Univers
from ..values import Instant, Vecteur3

State12 = tuple[Vecteur3, Vecteur3, Vecteur3, Vecteur3]


def _derivee(state: State12, m1: float, m2: float) -> State12:
    r1, v1, r2, v2 = state
    relative_acceleration = acceleration_relative_1pn(r2 - r1, v2 - v1, m1, m2, True)
    a1, a2 = repartir_acceleration_relative(relative_acceleration, m1, m2)
    return v1, a1, v2, a2


def _advance_stage(base: State12, derivative: State12, factor: float) -> State12:
    return tuple(base[i] + derivative[i] * factor for i in range(4))  # type: ignore[return-value]


@dataclass(slots=True)
class IntegrateurDeuxCorps1PNRK4:
    nom: str = "Runge-Kutta 4 deux-corps 1PN"

    def avancer(self, corps_1: CorpsPhysique, corps_2: CorpsPhysique, instant: Instant, dt_s: float) -> None:
        if dt_s <= 0:
            raise ValueError("Positive 1PN integration step required")
        state1 = corps_1.etat()
        state2 = corps_2.etat()
        if state1.translation is None or state2.translation is None:
            raise ValueError("1PN two-body integration requires classical translation coordinates")
        m1 = corps_1.masse().value
        m2 = corps_2.masse().value
        if m1 <= 0 or m2 <= 0:
            raise ValueError("1PN two-body integration requires positive masses")

        base: State12 = (
            state1.translation.position,
            state1.translation.vitesse,
            state2.translation.position,
            state2.translation.vitesse,
        )
        k1 = _derivee(base, m1, m2)
        k2 = _derivee(_advance_stage(base, k1, 0.5 * dt_s), m1, m2)
        k3 = _derivee(_advance_stage(base, k2, 0.5 * dt_s), m1, m2)
        k4 = _derivee(_advance_stage(base, k3, dt_s), m1, m2)
        final = tuple(
            base[i] + (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]) * (dt_s / 6.0)
            for i in range(4)
        )
        state1.translation = EtatTranslationnel(final[0], final[1])
        state2.translation = EtatTranslationnel(final[2], final[3])
        final_instant = Instant(instant.seconds + dt_s)
        state1.instant = final_instant
        state2.instant = final_instant


@dataclass(slots=True)
class Evolution1PNDeuxCorps:
    """Multi-regime adapter owning exactly one weak-field 1PN pair."""

    corps_1_id: str
    corps_2_id: str
    integrateur: IntegrateurDeuxCorps1PNRK4 = field(default_factory=IntegrateurDeuxCorps1PNRK4)
    regime: RegimeDynamique = field(default=RegimeDynamique.POST_NEWTONIEN_1PN, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return (self.corps_1_id, self.corps_2_id)

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        body1 = univers.trouver_corps(self.corps_1_id)
        body2 = univers.trouver_corps(self.corps_2_id)
        self.integrateur.avancer(body1, body2, instant, dt_s)
        return []
