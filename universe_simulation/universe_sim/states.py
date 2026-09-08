"""Dynamic physical state objects."""
from __future__ import annotations

from dataclasses import dataclass, field

from .spacetime import COORDONNEES_CARTESIENNES, REFERENTIEL_INERTIEL, Referentiel, SystemeCoordonnees
from .values import GrandeurPhysique, Instant, Quaternion, Vecteur3


@dataclass(slots=True)
class EtatTranslationnel:
    position: Vecteur3 = field(default_factory=Vecteur3.zero)
    vitesse: Vecteur3 = field(default_factory=Vecteur3.zero)


@dataclass(slots=True)
class EtatRotationnel:
    orientation: Quaternion = field(default_factory=Quaternion.identity)
    vitesse_angulaire: Vecteur3 = field(default_factory=Vecteur3.zero)

    def normaliser_orientation(self) -> None:
        self.orientation = self.orientation.normalized()

    def rotation_matrix(self) -> tuple[tuple[float, float, float], ...]:
        q = self.orientation.normalized()
        w, x, y, z = q.w, q.x, q.y, q.z
        return (
            (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
        )


@dataclass(slots=True)
class EtatMassique:
    masse: GrandeurPhysique

    def __post_init__(self) -> None:
        self.masse.require_non_negative()

    def est_positive(self) -> bool:
        return self.masse.value > 0


@dataclass(slots=True)
class EtatElectrique:
    charge_nette: GrandeurPhysique = field(default_factory=lambda: GrandeurPhysique(0.0, "C"))
    moment_dipolaire_electrique: Vecteur3 | None = None


@dataclass(slots=True)
class EtatPhysique:
    instant: Instant
    referentiel: Referentiel = field(default_factory=lambda: REFERENTIEL_INERTIEL)
    systeme_coordonnees: SystemeCoordonnees = field(default_factory=lambda: COORDONNEES_CARTESIENNES)
    translation: EtatTranslationnel | None = None
    rotation: EtatRotationnel | None = None
    massique: EtatMassique | None = None
    electrique: EtatElectrique | None = None

    def copier(self) -> "EtatPhysique":
        return EtatPhysique(
            instant=Instant(self.instant.seconds),
            referentiel=self.referentiel,
            systeme_coordonnees=self.systeme_coordonnees,
            translation=None if self.translation is None else EtatTranslationnel(self.translation.position, self.translation.vitesse),
            rotation=None if self.rotation is None else EtatRotationnel(self.rotation.orientation, self.rotation.vitesse_angulaire),
            massique=None if self.massique is None else EtatMassique(GrandeurPhysique(self.massique.masse.value, self.massique.masse.unit, self.massique.masse.uncertainty)),
            electrique=None if self.electrique is None else EtatElectrique(self.electrique.charge_nette, self.electrique.moment_dipolaire_electrique),
        )

    def est_complet_pour(self, modele: object) -> bool:
        required = getattr(modele, "required_state_components", ("translation", "massique"))
        return all(getattr(self, name, None) is not None for name in required)


@dataclass(slots=True)
class DeriveeEtat:
    d_position: Vecteur3 = field(default_factory=Vecteur3.zero)
    d_vitesse: Vecteur3 = field(default_factory=Vecteur3.zero)
    d_orientation: Quaternion = field(default_factory=lambda: Quaternion(0.0, 0.0, 0.0, 0.0))
    d_vitesse_angulaire: Vecteur3 = field(default_factory=Vecteur3.zero)
    d_masse: float = 0.0
    d_charge: float = 0.0

    def additionner(self, autre: "DeriveeEtat") -> None:
        self.d_position = self.d_position + autre.d_position
        self.d_vitesse = self.d_vitesse + autre.d_vitesse
        self.d_orientation = self.d_orientation + autre.d_orientation
        self.d_vitesse_angulaire = self.d_vitesse_angulaire + autre.d_vitesse_angulaire
        self.d_masse += autre.d_masse
        self.d_charge += autre.d_charge

    def mettre_a_zero(self) -> None:
        self.d_position = Vecteur3.zero()
        self.d_vitesse = Vecteur3.zero()
        self.d_orientation = Quaternion(0.0, 0.0, 0.0, 0.0)
        self.d_vitesse_angulaire = Vecteur3.zero()
        self.d_masse = 0.0
        self.d_charge = 0.0
