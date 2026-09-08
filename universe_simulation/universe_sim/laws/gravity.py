"""Newtonian gravity models and classical corrections."""
from __future__ import annotations
from dataclasses import dataclass
from ..bodies import CorpsPhysique, Planete
from ..constants import G
from ..effects import EffetPhysique, Force
from ..systems import Univers
from ..values import Instant, Vecteur3
from .base import LoiPhysique, ModelePhysique

@dataclass(slots=True)
class GravitationNewtonienne(LoiPhysique):
    nom: str = "Gravitation newtonienne"
    domaine_validite: str = "weak field, non-relativistic classical dynamics"
    def force_entre(self, a: CorpsPhysique, b: CorpsPhysique, instant: Instant) -> tuple[Force, Force]:
        ta=a.etat().translation; tb=b.etat().translation
        if ta is None or tb is None: raise ValueError("Gravity requires translational states")
        displacement=tb.position-ta.position; r2=displacement.norm2()
        if r2 == 0: raise ValueError(f"Coincident centers for {a.nom} and {b.nom}; collision model required")
        r=r2**0.5; vector_ab=displacement*(G*a.masse().value*b.masse().value/(r2*r))
        return (Force(cible_id=a.id,source_id=b.id,instant=instant,loi_origine=self.nom,vecteur=vector_ab), Force(cible_id=b.id,source_id=a.id,instant=instant,loi_origine=self.nom,vecteur=-vector_ab))

@dataclass(slots=True)
class ModeleGravitationPonctuelle(ModelePhysique):
    nom: str = "Gravitation ponctuelle N-corps"
    domaine_validite: str = "Newtonian point-mass approximation"
    niveau_fidelite: str = "monopole"
    loi: GravitationNewtonienne = None  # type: ignore[assignment]
    def __post_init__(self) -> None:
        if self.loi is None: self.loi=GravitationNewtonienne()
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        bodies=[b for b in univers.corps_physiques if b.actif and b.etat().translation is not None and b.etat().massique is not None]
        pairs=gestionnaire_interactions.paires(bodies) if gestionnaire_interactions is not None and hasattr(gestionnaire_interactions,"paires") else ((bodies[i],bodies[j]) for i in range(len(bodies)) for j in range(i+1,len(bodies)))
        effects=[]
        for a,b in pairs:
            fa,fb=self.loi.force_entre(a,b,instant); effects.extend((fa,fb))
        return effects

@dataclass(slots=True)
class ModeleJ2(ModelePhysique):
    source_id: str = ""
    nom: str = "Correction gravitationnelle J2"
    domaine_validite: str = "Newtonian exterior field around an oblate primary"
    niveau_fidelite: str = "J2"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        source=univers.trouver_corps(self.source_id)
        if not isinstance(source,Planete) or source.j2 is None: return []
        radius=source.rayon_equatorial or source.rayon_reference; ts=source.etat().translation
        if radius is None or ts is None: return []
        mu=G*source.masse().value; R=radius.value; effects=[]
        for target in univers.corps_physiques:
            if target.id==source.id or not target.actif or target.etat().translation is None: continue
            rel=target.etat().translation.position-ts.position; r2=rel.norm2()
            if r2==0: continue
            r=r2**0.5; z2=(rel.z*rel.z)/r2; factor=1.5*source.j2*mu*R*R/(r**5)
            acc=Vecteur3(factor*rel.x*(5*z2-1),factor*rel.y*(5*z2-1),factor*rel.z*(5*z2-3))
            effects.append(Force(cible_id=target.id,source_id=source.id,instant=instant,loi_origine=self.nom,vecteur=acc*target.masse().value))
        return effects

@dataclass(slots=True)
class ModeleMultipolaire(ModelePhysique):
    sources_j2: tuple[str,...]=()
    nom: str="Modele gravitationnel multipolaire"
    domaine_validite: str="classical exterior gravity"
    niveau_fidelite: str="monopole + optional J2"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        effects=ModeleGravitationPonctuelle().evaluer(univers,instant,gestionnaire_interactions)
        for source_id in self.sources_j2: effects.extend(ModeleJ2(source_id=source_id).evaluer(univers,instant,gestionnaire_interactions))
        return effects
