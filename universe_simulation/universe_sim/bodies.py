"""Physical bodies: natural, artificial and astronomical specializations."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import pi
from uuid import uuid4

from .fields import Atmosphere, DistributionMatiere, Rayonnement, VentStellaire
from .states import EtatPhysique
from .values import GrandeurPhysique, Vecteur3


@dataclass(slots=True)
class CorpsPhysique:
    nom: str
    etat_courant: EtatPhysique
    rayon_reference: GrandeurPhysique | None = None
    forme_reference: str | None = "sphere"
    dimensions_reference: Vecteur3 | None = None
    distribution_masse: DistributionMatiere | None = None
    coefficient_trainee: float | None = None
    surface_reference: float | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    actif: bool = True
    historique: list[EtatPhysique] = field(default_factory=list)

    def etat(self) -> EtatPhysique:
        return self.etat_courant

    def masse(self) -> GrandeurPhysique:
        if self.etat_courant.massique is None:
            raise ValueError(f"{self.nom} has no mass state")
        return self.etat_courant.massique.masse

    def charge(self) -> GrandeurPhysique:
        if self.etat_courant.electrique is None:
            return GrandeurPhysique(0.0, "C")
        return self.etat_courant.electrique.charge_nette

    def dimensions(self) -> Vecteur3 | None:
        return self.dimensions_reference

    def possede_composants(self) -> bool:
        return False

    def volume_spherique(self) -> float | None:
        if self.rayon_reference is None:
            return None
        r = self.rayon_reference.value
        return 4.0 * pi * r**3 / 3.0

    def enregistrer_etat(self) -> None:
        self.historique.append(self.etat_courant.copier())


@dataclass(slots=True)
class CorpsNaturel(CorpsPhysique):
    composition_moyenne: dict[str, float] = field(default_factory=dict)
    moment_dipolaire_magnetique: Vecteur3 | None = None
    atmosphere: Atmosphere | None = None

    def possede_atmosphere(self) -> bool:
        return self.atmosphere is not None


@dataclass(slots=True)
class Etoile(CorpsNaturel):
    luminosite: GrandeurPhysique | None = None
    temperature_effective: GrandeurPhysique | None = None
    type_spectral: str | None = None
    rayonnement: Rayonnement | None = None
    vent_stellaire: VentStellaire | None = None

    def emet_rayonnement(self) -> bool:
        return self.luminosite is not None and self.luminosite.value > 0


@dataclass(slots=True)
class NaineBrune(CorpsNaturel):
    temperature_effective: GrandeurPhysique | None = None
    type_spectral: str | None = None


@dataclass(slots=True)
class Planete(CorpsNaturel):
    j2: float | None = None
    rayon_equatorial: GrandeurPhysique | None = None
    rayon_polaire: GrandeurPhysique | None = None
    albedo: float | None = None

    def aplatissement(self) -> float | None:
        if self.rayon_equatorial is None or self.rayon_polaire is None:
            return None
        re = self.rayon_equatorial.value
        return (re - self.rayon_polaire.value) / re if re else None


@dataclass(slots=True)
class PlaneteNaine(CorpsNaturel):
    albedo: float | None = None


@dataclass(slots=True)
class SatelliteNaturel(CorpsNaturel):
    corps_hote_id: str | None = None


@dataclass(slots=True)
class PetitCorps(CorpsNaturel):
    classe_spectrale: str | None = None


@dataclass(slots=True)
class Asteroide(PetitCorps):
    famille: str | None = None


@dataclass(slots=True)
class Comete(PetitCorps):
    activite_cometaire: bool = False
    taux_degagement_gaz: float | None = None


@dataclass(slots=True)
class Meteoroide(PetitCorps):
    pass


class TypeClassificationAstronomique(str, Enum):
    TRANSNEPTUNIEN = "transneptunien"
    INTERSTELLAIRE = "interstellaire"
    PULSAR = "pulsar"
    MAGNETAR = "magnetar"


@dataclass(frozen=True, slots=True)
class ClassificationAstronomique:
    type: TypeClassificationAstronomique
    parametres: dict[str, float | str] = field(default_factory=dict)


@dataclass(slots=True)
class ObjetInterstellaire(PetitCorps):
    classification: ClassificationAstronomique = field(default_factory=lambda: ClassificationAstronomique(TypeClassificationAstronomique.INTERSTELLAIRE))


@dataclass(slots=True)
class ObjetTransneptunien(PetitCorps):
    classification: ClassificationAstronomique = field(default_factory=lambda: ClassificationAstronomique(TypeClassificationAstronomique.TRANSNEPTUNIEN))


@dataclass(slots=True)
class ResiduStellaire(CorpsNaturel):
    age_refroidissement: GrandeurPhysique | None = None


@dataclass(slots=True)
class NaineBlanche(ResiduStellaire):
    composition_coeur: str | None = None


@dataclass(slots=True)
class EtoileNeutrons(ResiduStellaire):
    champ_magnetique_surface: GrandeurPhysique | None = None
    periode_rotation: GrandeurPhysique | None = None
    classifications: list[ClassificationAstronomique] = field(default_factory=list)

    def est_pulsar(self) -> bool:
        return any(c.type == TypeClassificationAstronomique.PULSAR for c in self.classifications)

    def est_magnetar(self) -> bool:
        return any(c.type == TypeClassificationAstronomique.MAGNETAR for c in self.classifications)


@dataclass(frozen=True, slots=True)
class Pulsar:
    periode: GrandeurPhysique
    derivee_periode: float | None = None


@dataclass(frozen=True, slots=True)
class Magnetar:
    champ_magnetique_surface: GrandeurPhysique


@dataclass(slots=True)
class TrouNoir(CorpsNaturel):
    moment_cinetique_spin: Vecteur3 = field(default_factory=Vecteur3.zero)
    charge_bh: GrandeurPhysique = field(default_factory=lambda: GrandeurPhysique(0.0, "C"))

    def parametre_spin(self) -> float:
        from .constants import C, G
        m = self.masse().value
        j = self.moment_cinetique_spin.norm()
        return 0.0 if m == 0 else C * j / (G * m * m)


@dataclass(slots=True)
class CorpsArtificiel(CorpsPhysique):
    fabricant: str | None = None


@dataclass(slots=True)
class Vehicule(CorpsArtificiel):
    masse_propergol: GrandeurPhysique | None = None
    poussee_max: GrandeurPhysique | None = None
    impulsion_specifique: GrandeurPhysique | None = None

    def propergol_disponible(self) -> float:
        return 0.0 if self.masse_propergol is None else self.masse_propergol.value


@dataclass(slots=True)
class SatelliteArtificiel(CorpsArtificiel):
    surface_panneaux: float | None = None


@dataclass(slots=True)
class SondeSpatiale(Vehicule):
    pass


@dataclass(slots=True)
class StationSpatiale(CorpsArtificiel):
    modules_connectes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Module(CorpsArtificiel):
    parent_id: str | None = None


@dataclass(slots=True)
class DebrisSpatial(CorpsArtificiel):
    origine_id: str | None = None


@dataclass(slots=True)
class CompositionPhysique:
    ensemble: CorpsPhysique
    composant: CorpsPhysique
    liaison: str = "rigide"
    position_relative: Vecteur3 = field(default_factory=Vecteur3.zero)
    active: bool = True

    def __post_init__(self) -> None:
        if self.ensemble.id == self.composant.id:
            raise ValueError("A physical body cannot directly contain itself")
