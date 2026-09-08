"""External geometry and frame transformation services."""
from __future__ import annotations
from dataclasses import dataclass
from ..spacetime import Referentiel, SystemeCoordonnees, TypeCoordonnees, cartesien_vers_spherique, spherique_vers_cartesien
from ..states import EtatPhysique, EtatTranslationnel
from ..values import Instant, Quaternion, Vecteur3

@dataclass(frozen=True, slots=True)
class PoseReferentiel:
    origine: Vecteur3; orientation: Quaternion; vitesse_origine: Vecteur3; vitesse_angulaire: Vecteur3

def pose_dans_racine(ref: Referentiel, instant: Instant) -> PoseReferentiel:
    local_o=ref.origine_a(instant); local_q=ref.orientation_a(instant); local_v=ref.vitesse_origine_a(instant); local_w=ref.vitesse_angulaire
    if ref.parent is None: return PoseReferentiel(local_o,local_q,local_v,local_w)
    parent=pose_dans_racine(ref.parent,instant); rotated_o=parent.orientation.rotate(local_o)
    return PoseReferentiel(parent.origine+rotated_o,(parent.orientation*local_q).normalized(),parent.vitesse_origine+parent.vitesse_angulaire.cross(rotated_o)+parent.orientation.rotate(local_v),parent.vitesse_angulaire+parent.orientation.rotate(local_w))

def transformer_position(position: Vecteur3, source: Referentiel, cible: Referentiel, instant: Instant) -> Vecteur3:
    ps=pose_dans_racine(source,instant); pt=pose_dans_racine(cible,instant); p_root=ps.origine+ps.orientation.rotate(position)
    return pt.orientation.conjugate().normalized().rotate(p_root-pt.origine)

def transformer_vitesse(position: Vecteur3, vitesse: Vecteur3, source: Referentiel, cible: Referentiel, instant: Instant) -> Vecteur3:
    ps=pose_dans_racine(source,instant); pt=pose_dans_racine(cible,instant); p_root_rel=ps.orientation.rotate(position)
    v_root=ps.vitesse_origine+ps.vitesse_angulaire.cross(p_root_rel)+ps.orientation.rotate(vitesse); p_target=transformer_position(position,source,cible,instant)
    v_target=pt.orientation.conjugate().normalized().rotate(v_root-pt.vitesse_origine); omega=pt.orientation.conjugate().normalized().rotate(pt.vitesse_angulaire)
    return v_target-omega.cross(p_target)

def transformer_etat(etat: EtatPhysique, referentiel_cible: Referentiel) -> EtatPhysique:
    new=etat.copier(); new.referentiel=referentiel_cible
    if etat.translation is not None:
        new.translation=EtatTranslationnel(transformer_position(etat.translation.position,etat.referentiel,referentiel_cible,etat.instant),transformer_vitesse(etat.translation.position,etat.translation.vitesse,etat.referentiel,referentiel_cible,etat.instant))
    return new

def convertir_coordonnees(position, source: SystemeCoordonnees, cible: SystemeCoordonnees):
    if source.type==cible.type: return position
    if source.type==TypeCoordonnees.CARTESIEN and cible.type==TypeCoordonnees.SPHERIQUE:
        return cartesien_vers_spherique(position if isinstance(position,Vecteur3) else Vecteur3.from_iterable(position))
    if source.type==TypeCoordonnees.SPHERIQUE and cible.type==TypeCoordonnees.CARTESIEN:
        values=position.as_tuple() if isinstance(position,Vecteur3) else position; return spherique_vers_cartesien(*values)
    raise NotImplementedError(f"Coordinate conversion {source.type} -> {cible.type} is not implemented")

def position_relative(a: EtatPhysique,b: EtatPhysique)->Vecteur3:
    if a.translation is None or b.translation is None: raise ValueError("Relative position requires translational states")
    if a.referentiel.id!=b.referentiel.id: b=transformer_etat(b,a.referentiel)
    return b.translation.position-a.translation.position

def vitesse_relative(a: EtatPhysique,b: EtatPhysique)->Vecteur3:
    if a.translation is None or b.translation is None: raise ValueError("Relative velocity requires translational states")
    if a.referentiel.id!=b.referentiel.id: b=transformer_etat(b,a.referentiel)
    return b.translation.vitesse-a.translation.vitesse
