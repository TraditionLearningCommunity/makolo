"""Hierarchical inertial frames with Poincare/Lorentz transformations.

This registry is intended for transitions between large-scale numerical frames
(e.g. group-of-galaxies -> galaxy -> local stellar-system frame). It transforms
individual space-time events and four-momenta exactly in flat space-time.

It deliberately does not pretend that an entire spatial snapshot can be moved
between relativistic frames while preserving simultaneity: simultaneity is
frame-dependent. Large arrays should therefore stay authoritative in their own
frame and individual bodies should be transformed at explicit transition
events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from ..constants import C
from ..relativistic_values import Quadrimpulsion
from ..values import Vecteur3
from .relativistic_geometry import (
    EvenementMinkowski,
    transformer_evenement_lorentz,
    transformer_quadrimpulsion_lorentz,
    transformation_inverse_evenement,
)


@dataclass(frozen=True, slots=True)
class CadreInertielRelatif:
    nom: str
    parent_id: str | None = None
    origine_dans_parent: EvenementMinkowski = EvenementMinkowski(0.0, Vecteur3.zero())
    vitesse_dans_parent: Vecteur3 = Vecteur3.zero()
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.vitesse_dans_parent.norm() >= C:
            raise ValueError("An inertial frame must move subluminally relative to its parent")
        if self.parent_id is None:
            if self.vitesse_dans_parent.norm2() != 0 or self.origine_dans_parent != EvenementMinkowski(0.0, Vecteur3.zero()):
                raise ValueError("Root inertial frame must have zero relative origin event and velocity")


@dataclass(slots=True)
class RegistreCadresInertiels:
    racine: CadreInertielRelatif
    cadres: dict[str, CadreInertielRelatif] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        if self.racine.parent_id is not None:
            raise ValueError("Root frame cannot have a parent")
        self.cadres[self.racine.id] = self.racine

    def ajouter(self, cadre: CadreInertielRelatif) -> None:
        if cadre.id in self.cadres:
            raise ValueError(f"Duplicate inertial frame id: {cadre.id}")
        if cadre.parent_id is None or cadre.parent_id not in self.cadres:
            raise ValueError("A non-root inertial frame must reference an existing parent")
        ancestor = cadre.parent_id
        while ancestor is not None:
            if ancestor == cadre.id:
                raise ValueError("Cycle in inertial frame hierarchy")
            ancestor = self.cadres[ancestor].parent_id
        self.cadres[cadre.id] = cadre

    def obtenir(self, cadre_id: str) -> CadreInertielRelatif:
        try:
            return self.cadres[cadre_id]
        except KeyError as exc:
            raise KeyError(f"Unknown inertial frame: {cadre_id}") from exc

    def _chaine_vers_racine(self, cadre_id: str) -> tuple[CadreInertielRelatif, ...]:
        chain = []
        current = self.obtenir(cadre_id)
        while current.parent_id is not None:
            chain.append(current)
            current = self.obtenir(current.parent_id)
        if current.id != self.racine.id:
            raise ValueError("Frame does not belong to this registry root")
        return tuple(chain)

    @staticmethod
    def _local_vers_parent(cadre: CadreInertielRelatif, event: EvenementMinkowski) -> EvenementMinkowski:
        relative_parent = transformation_inverse_evenement(event, cadre.vitesse_dans_parent)
        return EvenementMinkowski(
            relative_parent.t_s + cadre.origine_dans_parent.t_s,
            relative_parent.position_m + cadre.origine_dans_parent.position_m,
        )

    @staticmethod
    def _parent_vers_local(cadre: CadreInertielRelatif, event: EvenementMinkowski) -> EvenementMinkowski:
        relative_parent = EvenementMinkowski(
            event.t_s - cadre.origine_dans_parent.t_s,
            event.position_m - cadre.origine_dans_parent.position_m,
        )
        return transformer_evenement_lorentz(relative_parent, cadre.vitesse_dans_parent)

    def evenement_vers_racine(self, event: EvenementMinkowski, source_id: str) -> EvenementMinkowski:
        result = event
        for frame in self._chaine_vers_racine(source_id):
            result = self._local_vers_parent(frame, result)
        return result

    def evenement_depuis_racine(self, event: EvenementMinkowski, cible_id: str) -> EvenementMinkowski:
        result = event
        chain = self._chaine_vers_racine(cible_id)
        for frame in reversed(chain):
            result = self._parent_vers_local(frame, result)
        return result

    def transformer_evenement(self, event: EvenementMinkowski, source_id: str, cible_id: str) -> EvenementMinkowski:
        if source_id == cible_id:
            return event
        return self.evenement_depuis_racine(self.evenement_vers_racine(event, source_id), cible_id)

    def quadrimpulsion_vers_racine(self, p: Quadrimpulsion, source_id: str) -> Quadrimpulsion:
        result = p
        for frame in self._chaine_vers_racine(source_id):
            result = transformer_quadrimpulsion_lorentz(result, -frame.vitesse_dans_parent)
        return result

    def quadrimpulsion_depuis_racine(self, p: Quadrimpulsion, cible_id: str) -> Quadrimpulsion:
        result = p
        for frame in reversed(self._chaine_vers_racine(cible_id)):
            result = transformer_quadrimpulsion_lorentz(result, frame.vitesse_dans_parent)
        return result

    def transformer_quadrimpulsion(self, p: Quadrimpulsion, source_id: str, cible_id: str) -> Quadrimpulsion:
        if source_id == cible_id:
            return p
        return self.quadrimpulsion_depuis_racine(self.quadrimpulsion_vers_racine(p, source_id), cible_id)
