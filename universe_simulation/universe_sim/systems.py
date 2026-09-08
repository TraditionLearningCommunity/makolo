"""Physical systems, galaxies and the universe container."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .bodies import CorpsPhysique, Etoile
from .fields import DistributionMatiere
from .spacetime import ModeleEspaceTemps, ModeleEspaceTempsClassique
from .values import Vecteur3


@dataclass(slots=True)
class SystemePhysique:
    nom: str
    membres: list[CorpsPhysique] = field(default_factory=list)
    sous_systemes: list["SystemePhysique"] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))

    def ajouter_membre(self, corps: CorpsPhysique) -> None:
        if all(existing.id != corps.id for existing in self.membres):
            self.membres.append(corps)

    def retirer_membre(self, corps_id: str) -> None:
        self.membres = [c for c in self.membres if c.id != corps_id]

    def ajouter_sous_systeme(self, systeme: "SystemePhysique") -> None:
        if systeme.id == self.id:
            raise ValueError("A system cannot contain itself")
        if all(existing.id != systeme.id for existing in self.sous_systemes):
            self.sous_systemes.append(systeme)

    def corps(self) -> tuple[CorpsPhysique, ...]:
        return tuple(self.membres)


@dataclass(slots=True)
class SystemeGravitationnel(SystemePhysique):
    gravitationnellement_lie: bool | None = None


@dataclass(slots=True)
class SystemeStellaire(SystemeGravitationnel):
    def etoiles(self) -> tuple[Etoile, ...]:
        return tuple(c for c in self.membres if isinstance(c, Etoile))

    def valider(self) -> bool:
        return len(self.etoiles()) >= 1


@dataclass(slots=True)
class SystemePlanetaire(SystemeGravitationnel):
    composantes_dominantes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AmasStellaire(SystemeGravitationnel):
    type_amas: str | None = None


@dataclass(slots=True)
class Galaxie(SystemeGravitationnel):
    type_morphologique: str | None = None
    distribution_diffuse: DistributionMatiere | None = None
    rayon_caracteristique: float | None = None


@dataclass(slots=True)
class GroupeGalaxies(SystemeGravitationnel):
    galaxies: list[Galaxie] = field(default_factory=list)


@dataclass(slots=True)
class AmasGalaxies(SystemeGravitationnel):
    galaxies: list[Galaxie] = field(default_factory=list)


@dataclass(slots=True)
class StructureCosmique:
    nom: str
    type_structure: str
    centre: Vecteur3 | None = None
    echelle: float | None = None
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class Univers:
    nom: str = "Univers simule"
    modele_espace_temps: ModeleEspaceTemps = field(default_factory=ModeleEspaceTempsClassique)
    corps_physiques: list[CorpsPhysique] = field(default_factory=list)
    systemes_physiques: list[SystemePhysique] = field(default_factory=list)
    structures_observationnelles: list[object] = field(default_factory=list)
    champs: list[object] = field(default_factory=list)
    constantes_physiques: str = "CODATA/SI"
    id: str = field(default_factory=lambda: str(uuid4()))

    def ajouter_corps(self, corps: CorpsPhysique) -> None:
        if all(existing.id != corps.id for existing in self.corps_physiques):
            self.corps_physiques.append(corps)

    def ajouter_systeme(self, systeme: SystemePhysique) -> None:
        if all(existing.id != systeme.id for existing in self.systemes_physiques):
            self.systemes_physiques.append(systeme)

    def corps(self) -> tuple[CorpsPhysique, ...]:
        return tuple(self.corps_physiques)

    def systemes(self) -> tuple[SystemePhysique, ...]:
        return tuple(self.systemes_physiques)

    def trouver_corps(self, identifiant_ou_nom: str) -> CorpsPhysique:
        for corps in self.corps_physiques:
            if corps.id == identifiant_ou_nom or corps.nom == identifiant_ou_nom:
                return corps
        raise KeyError(identifiant_ou_nom)
