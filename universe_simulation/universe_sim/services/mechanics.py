"""External mechanics and gravity-derived calculations."""
from __future__ import annotations
from math import sqrt
from ..bodies import CorpsPhysique
from ..constants import G
from ..systems import SystemePhysique
from ..values import Instant,Vecteur3

def calculer_barycentre(systeme: SystemePhysique, instant: Instant|None=None)->Vecteur3:
    weighted=Vecteur3.zero(); total=0.0
    for body in systeme.membres:
        state=body.etat()
        if state.translation is None: continue
        m=body.masse().value; total+=m; weighted=weighted+state.translation.position*m
    if total<=0: raise ValueError("Barycenter requires positive total mass")
    return weighted/total

def centre_de_masse(corps:list[CorpsPhysique])->Vecteur3: return calculer_barycentre(SystemePhysique("temporary",membres=corps))
def force_gravitationnelle(a:CorpsPhysique,b:CorpsPhysique)->Vecteur3:
    ta,tb=a.etat().translation,b.etat().translation
    if ta is None or tb is None: raise ValueError("Translational states required")
    dr=tb.position-ta.position; r2=dr.norm2()
    if r2==0: raise ValueError("Coincident centers")
    return dr*(G*a.masse().value*b.masse().value/(r2*sqrt(r2)))
def energie_cinetique(c:CorpsPhysique)->float:
    t=c.etat().translation; return 0.0 if t is None else 0.5*c.masse().value*t.vitesse.norm2()
def energie_potentielle_gravitationnelle(a:CorpsPhysique,b:CorpsPhysique)->float:
    ta,tb=a.etat().translation,b.etat().translation
    if ta is None or tb is None: return 0.0
    r=ta.position.distance_to(tb.position)
    if r==0: raise ValueError("Coincident centers")
    return -G*a.masse().value*b.masse().value/r
def energie_mecanique_totale(corps:list[CorpsPhysique])->float:
    active=[c for c in corps if c.actif]; total=sum(energie_cinetique(c) for c in active)
    for i in range(len(active)):
        for j in range(i+1,len(active)): total+=energie_potentielle_gravitationnelle(active[i],active[j])
    return total
def quantite_mouvement_totale(corps:list[CorpsPhysique])->Vecteur3:
    p=Vecteur3.zero()
    for b in corps:
        t=b.etat().translation
        if b.actif and t is not None: p=p+t.vitesse*b.masse().value
    return p
def moment_cinetique_total(corps:list[CorpsPhysique],origine:Vecteur3|None=None)->Vecteur3:
    o=origine or Vecteur3.zero(); L=Vecteur3.zero()
    for b in corps:
        t=b.etat().translation
        if b.actif and t is not None: L=L+(t.position-o).cross(t.vitesse*b.masse().value)
    return L
def vitesse_liberation(masse_centrale:float,rayon:float)->float:
    if rayon<=0: raise ValueError("Radius must be positive")
    return sqrt(2*G*masse_centrale/rayon)
