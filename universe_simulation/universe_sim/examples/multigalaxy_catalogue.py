"""Deterministic compact catalogue for the multi-galaxy scenario."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from math import pi
import numpy as np

from ..bodies import Asteroide, Comete, DebrisSpatial, Etoile, Planete, SatelliteNaturel
from ..constants import AU, C, EARTH_MASS, EARTH_RADIUS, G, SOLAR_MASS, SOLAR_RADIUS
from ..regimes import NiveauActiviteCalcul
from ..services.inertial_frames import CadreInertielRelatif, RegistreCadresInertiels
from ..services.relativistic_geometry import EvenementMinkowski
from ..simulation.array_backend import ArrayStateBackend
from ..spacetime import ClassificationReferentiel, PointReference, Referentiel
from ..states import EtatMassique, EtatPhysique, EtatTranslationnel
from ..systems import SystemeStellaire, Univers
from ..values import GrandeurPhysique, Instant, Vecteur3

PARSEC_M = 3.085677581491367e16
KPC_M = 1e3 * PARSEC_M
MPC_M = 1e6 * PARSEC_M

class TypeEntiteCatalogue(IntEnum):
    TROU_NOIR=0; ETOILE=1; PLANETE=2; SATELLITE_NATUREL=3; ASTEROIDE=4; COMETE=5; DEBRIS_ARTIFICIEL=6; VEHICULE_SR=7

class TypeCadreCatalogue(IntEnum):
    GROUPE_GALACTIQUE=0; GALAXIE=1; SYSTEME_STELLAIRE=2

_NIVEAU_CODE = {
    NiveauActiviteCalcul.ACTIVE:0, NiveauActiviteCalcul.ANALYTIC:1,
    NiveauActiviteCalcul.AGGREGATED:2, NiveauActiviteCalcul.TRACER:3,
    NiveauActiviteCalcul.VISUAL_ONLY:4,
}
_CODE_NIVEAU = {v:k for k,v in _NIVEAU_CODE.items()}

@dataclass(frozen=True, slots=True)
class ConfigurationMultiGalaxies:
    nom: str
    nombre_galaxies: int
    nombre_systemes: int
    nombre_entites: int
    nombre_vaisseaux_sr: int
    seed: int = 20_260_910
    def __post_init__(self):
        if self.nombre_galaxies < 1 or self.nombre_systemes < self.nombre_galaxies or self.nombre_entites < 1:
            raise ValueError("Invalid multi-galaxy scale")
        if not 0 <= self.nombre_vaisseaux_sr < self.nombre_entites:
            raise ValueError("Invalid relativistic vehicle count")

CONFIGURATIONS_MULTI_GALAXIES = {
    "mini": ConfigurationMultiGalaxies("mini",3,45,5_000,120),
    "10k": ConfigurationMultiGalaxies("10k",5,100,10_000,300),
    "100k": ConfigurationMultiGalaxies("100k",10,600,100_000,1_500),
    "500k": ConfigurationMultiGalaxies("500k",10,2_400,500_000,5_000),
}

def compteurs_configuration(c):
    g,s = c.nombre_galaxies,c.nombre_systemes
    result = {"black_holes":g,"stars":s+round(.15*s),"planets":8*s,"moons":20*s,"comets":5*s,"debris":round(12.5*s),"ships":c.nombre_vaisseaux_sr}
    result["asteroids"] = c.nombre_entites - sum(result.values())
    if result["asteroids"] < 0: raise ValueError("Scale too small for structural population")
    return result

def _unit(rng,n):
    v=rng.normal(size=(n,3)); d=np.linalg.norm(v,axis=1); d[d==0]=1; return v/d[:,None]

def _circular(rng,mu,r):
    d=_unit(rng,len(r)); d[:,2]*=.08; d/=np.linalg.norm(d,axis=1)[:,None]
    t=np.cross(np.repeat(np.array([[0.,0.,1.]]),len(r),axis=0),d); bad=np.linalg.norm(t,axis=1)<1e-12
    if bad.any(): t[bad]=np.cross(np.array([1.,0.,0.]),d[bad])
    t/=np.linalg.norm(t,axis=1)[:,None]; return d*r[:,None], t*np.sqrt(np.asarray(mu)/r)[:,None]

def _spectral(ms):
    return "O" if ms>=16 else "B" if ms>=2.1 else "A" if ms>=1.4 else "F" if ms>=1.04 else "G" if ms>=.8 else "K" if ms>=.45 else "M"

@dataclass(slots=True)
class CatalogueMultiGalaxies:
    configuration: ConfigurationMultiGalaxies
    tranches: dict[str,slice]
    morphologies_galaxies: tuple[str,...]
    positions_galaxies_m: np.ndarray; vitesses_galaxies_m_s: np.ndarray; masses_galaxies_kg: np.ndarray; rayons_galaxies_m: np.ndarray
    galaxie_par_systeme: np.ndarray; positions_systemes_dans_galaxie_m: np.ndarray; vitesses_systemes_dans_galaxie_m_s: np.ndarray
    types_entites: np.ndarray; types_cadres: np.ndarray; indices_cadres: np.ndarray; indices_parents: np.ndarray
    positions_locales_m: np.ndarray; vitesses_locales_m_s: np.ndarray; masses_kg: np.ndarray; rayons_m: np.ndarray; niveaux_activite: np.ndarray
    impulsions_vaisseaux_kg_m_s: np.ndarray; beta_vaisseaux: np.ndarray; origines_systemes_vaisseaux: np.ndarray; cibles_systemes_vaisseaux: np.ndarray; cibles_galaxies_vaisseaux: np.ndarray
    modes_mission_vaisseaux: np.ndarray; delta_rapidite_vaisseaux: np.ndarray; fraction_acceleration_vaisseaux: np.ndarray; fraction_deceleration_vaisseaux: np.ndarray

    @property
    def nombre_entites(self): return len(self.types_entites)
    def compteurs(self): return {k:v.stop-v.start for k,v in self.tranches.items()}
    def niveau(self,index): return _CODE_NIVEAU[int(self.niveaux_activite[index])]
    def memoire_tableaux_octets(self):
        arrays=(self.positions_galaxies_m,self.vitesses_galaxies_m_s,self.masses_galaxies_kg,self.rayons_galaxies_m,self.galaxie_par_systeme,self.positions_systemes_dans_galaxie_m,self.vitesses_systemes_dans_galaxie_m_s,self.types_entites,self.types_cadres,self.indices_cadres,self.indices_parents,self.positions_locales_m,self.vitesses_locales_m_s,self.masses_kg,self.rayons_m,self.niveaux_activite,self.impulsions_vaisseaux_kg_m_s,self.beta_vaisseaux,self.origines_systemes_vaisseaux,self.cibles_systemes_vaisseaux,self.cibles_galaxies_vaisseaux,self.modes_mission_vaisseaux,self.delta_rapidite_vaisseaux,self.fraction_acceleration_vaisseaux,self.fraction_deceleration_vaisseaux)
        return int(sum(v.nbytes for v in arrays))
    @staticmethod
    def id_galaxie(i): return f"galaxy-{i:03d}"
    @staticmethod
    def id_systeme(i): return f"system-{i:06d}"
    @staticmethod
    def id_corps(i): return f"body-{i:07d}"
    @staticmethod
    def id_vaisseau(i): return f"ship-{i:06d}"
    @staticmethod
    def id_cadre_galaxie(i): return f"frame-galaxy-{i:03d}"
    @staticmethod
    def id_cadre_systeme(i): return f"frame-system-{i:06d}"

    def construire_registre_cadres(self):
        root=CadreInertielRelatif("Groupe galactique",id="frame-group"); reg=RegistreCadresInertiels(root)
        for i in range(self.configuration.nombre_galaxies):
            reg.ajouter(CadreInertielRelatif(f"Galaxie {i+1}",root.id,EvenementMinkowski(0.,Vecteur3.from_iterable(self.positions_galaxies_m[i])),Vecteur3.from_iterable(self.vitesses_galaxies_m_s[i]),self.id_cadre_galaxie(i)))
        for i in range(self.configuration.nombre_systemes):
            g=int(self.galaxie_par_systeme[i]); reg.ajouter(CadreInertielRelatif(f"Systeme {i+1}",self.id_cadre_galaxie(g),EvenementMinkowski(0.,Vecteur3.from_iterable(self.positions_systemes_dans_galaxie_m[i])),Vecteur3.from_iterable(self.vitesses_systemes_dans_galaxie_m_s[i]),self.id_cadre_systeme(i)))
        return reg

    def backend_galaxies(self):
        n=self.configuration.nombre_galaxies; m=self.masses_galaxies_kg.copy(); v=self.vitesses_galaxies_m_s.copy()
        return ArrayStateBackend(tuple(self.id_galaxie(i) for i in range(n)),self.positions_galaxies_m.copy(),v,v*m[:,None],m,np.zeros(n),np.full(n,np.nan),np.ones(n,bool),np.zeros(n,np.int8),np.ones(n,bool))

    def backend_vaisseaux_sr(self):
        sl=self.tranches["ships"]; n=sl.stop-sl.start; m=self.masses_kg[sl].copy()
        return ArrayStateBackend(tuple(self.id_vaisseau(i) for i in range(n)),self.positions_locales_m[sl].copy(),self.vitesses_locales_m_s[sl].copy(),self.impulsions_vaisseaux_kg_m_s.copy(),m,np.zeros(n),np.zeros(n),np.ones(n,bool),np.ones(n,np.int8),np.ones(n,bool))

    def indices_entites_systeme(self,i):
        if not 0<=i<self.configuration.nombre_systemes: raise IndexError(i)
        return np.flatnonzero((self.types_cadres==int(TypeCadreCatalogue.SYSTEME_STELLAIRE))&(self.indices_cadres==i))

    def materialiser_systeme(self,i):
        idx=self.indices_entites_systeme(i); frame=Referentiel(f"Referentiel local systeme {i+1}",PointReference(f"Barycentre local systeme {i+1}"),classification=ClassificationReferentiel.APPROXIMATIVEMENT_INERTIEL); members=[]
        for j in idx:
            typ=TypeEntiteCatalogue(int(self.types_entites[j])); state=EtatPhysique(Instant(0.),referentiel=frame,translation=EtatTranslationnel(Vecteur3.from_iterable(self.positions_locales_m[j]),Vecteur3.from_iterable(self.vitesses_locales_m_s[j])),massique=EtatMassique(GrandeurPhysique(float(self.masses_kg[j]),"kg")))
            common=dict(nom=f"{typ.name.lower()}-{j:07d}",etat_courant=state,rayon_reference=GrandeurPhysique(float(self.rayons_m[j]),"m"),id=self.id_corps(int(j)))
            if typ==TypeEntiteCatalogue.ETOILE: body=Etoile(**common,type_spectral=_spectral(float(self.masses_kg[j]/SOLAR_MASS)))
            elif typ==TypeEntiteCatalogue.PLANETE: body=Planete(**common)
            elif typ==TypeEntiteCatalogue.SATELLITE_NATUREL: body=SatelliteNaturel(**common,corps_hote_id=self.id_corps(int(self.indices_parents[j])))
            elif typ==TypeEntiteCatalogue.ASTEROIDE: body=Asteroide(**common,famille="population synthetique")
            elif typ==TypeEntiteCatalogue.COMETE: body=Comete(**common,activite_cometaire=True)
            elif typ==TypeEntiteCatalogue.DEBRIS_ARTIFICIEL: body=DebrisSpatial(**common)
            else: continue
            members.append(body)
        return SystemeStellaire(f"Systeme stellaire {i+1}",membres=members,id=self.id_systeme(i),gravitationnellement_lie=True)

    def materialiser_systeme_dans_univers(self,i,univers:Univers):
        system=self.materialiser_systeme(i)
        for body in system.membres: univers.ajouter_corps(body)
        univers.ajouter_systeme(system); return system

def generer_catalogue_multi_galaxies(configuration="500k"):
    c=CONFIGURATIONS_MULTI_GALAXIES[configuration] if isinstance(configuration,str) else configuration; rng=np.random.default_rng(c.seed); cnt=compteurs_configuration(c); g,s=c.nombre_galaxies,c.nombre_systemes
    gd=_unit(rng,g); gpos=gd*(rng.uniform(.15,1.2,g)*MPC_M)[:,None]; gm=10**rng.uniform(np.log10(5e10),np.log10(2e12),g)*SOLAR_MASS; gr=rng.uniform(8,45,g)*KPC_M; gpos-=(gpos*gm[:,None]).sum(0)/gm.sum()
    rr=np.linalg.norm(gpos,axis=1); gv=np.cross(np.repeat(np.array([[0.,0.,1.]]),g,axis=0),gpos); bad=np.linalg.norm(gv,axis=1)<1e-20
    if bad.any(): gv[bad]=_unit(rng,bad.sum())
    gv/=np.linalg.norm(gv,axis=1)[:,None]; gv*= (np.sqrt(G*gm.sum()/np.maximum(rr,.1*MPC_M))*rng.uniform(.35,.8,g))[:,None]; gv-=(gv*gm[:,None]).sum(0)/gm.sum()
    morph=tuple(("spirale","spirale_barree","elliptique","spirale","irreguliere")[i%5] for i in range(g)); sg=np.arange(s,dtype=np.int32)%g; rng.shuffle(sg); spos=np.zeros((s,3)); sv=np.zeros((s,3))
    for gi in range(g):
        ix=np.flatnonzero(sg==gi); n=len(ix); R=gr[gi]
        if morph[gi]=="elliptique":
            r=R*np.power(rng.random(n),1/3)*.9; spos[ix]=_unit(rng,n)*r[:,None]; sv[ix]=rng.normal(0,np.sqrt(G*gm[gi]/R)*.45,size=(n,3)); continue
        r=np.minimum(rng.exponential(R/3,n),.95*R); ph=rng.uniform(0,2*pi,n); z=rng.normal(0,(.05 if morph[gi]=="irreguliere" else .02)*R,n); spos[ix]=np.column_stack((r*np.cos(ph),r*np.sin(ph),z)); a=R/5; menc=gm[gi]*r*r/np.maximum((r+a)**2,1); vc=np.sqrt(G*menc/np.maximum(r,.1*PARSEC_M)); sv[ix]=np.column_stack((-np.sin(ph)*vc,np.cos(ph)*vc,rng.normal(0,8e3,n)))

    N=c.nombre_entites; typ=np.empty(N,np.int8); fk=np.empty(N,np.int8); fi=np.empty(N,np.int32); parent=np.full(N,-1,np.int64); pos=np.zeros((N,3)); vel=np.zeros((N,3)); mass=np.zeros(N); rad=np.zeros(N); act=np.empty(N,np.int8); cursor=0; slices={}
    def alloc(name,n,t):
        nonlocal cursor
        sl=slice(cursor,cursor+n); slices[name]=sl; typ[sl]=int(t); cursor+=n; return sl

    sl=alloc("black_holes",cnt["black_holes"],TypeEntiteCatalogue.TROU_NOIR); fk[sl]=TypeCadreCatalogue.GALAXIE; fi[sl]=np.arange(g); mass[sl]=10**rng.uniform(6,9.3,g)*SOLAR_MASS; rad[sl]=2*G*mass[sl]/C**2; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.AGGREGATED]
    sl=alloc("stars",cnt["stars"],TypeEntiteCatalogue.ETOILE); stars=np.arange(sl.start,sl.stop); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.ANALYTIC]; primary=stars[:s]; fi[primary]=np.arange(s); mp=np.clip(rng.lognormal(np.log(.55),.8,s),.08,15)*SOLAR_MASS; mass[primary]=mp; rad[primary]=SOLAR_RADIUS*(mp/SOLAR_MASS)**.8
    nc=len(stars)-s; comp=stars[s:]; cs=rng.choice(s,nc,False); fi[comp]=cs; q=rng.uniform(.15,1,nc); mass[comp]=mp[cs]*q; rad[comp]=SOLAR_RADIUS*(mass[comp]/SOLAR_MASS)**.8; sep=10**rng.uniform(np.log10(.05*AU),np.log10(30*AU),nc); ph=rng.uniform(0,2*pi,nc); rel=np.column_stack((sep*np.cos(ph),sep*np.sin(ph),rng.normal(0,.01*sep))); mt=mp[cs]+mass[comp]; pos[primary[cs]]=-rel*(mass[comp]/mt)[:,None]; pos[comp]=rel*(mp[cs]/mt)[:,None]; omega=np.sqrt(G*mt/sep**3); vr=np.column_stack((-rel[:,1],rel[:,0],np.zeros(nc)))*omega[:,None]; vel[primary[cs]]=-vr*(mass[comp]/mt)[:,None]; vel[comp]=vr*(mp[cs]/mt)[:,None]; sm=mp.copy(); np.add.at(sm,cs,mass[comp])
    sl=alloc("planets",cnt["planets"],TypeEntiteCatalogue.PLANETE); pidx=np.arange(sl.start,sl.stop); ps=np.repeat(np.arange(s),8); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; fi[sl]=ps; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.ANALYTIC]; slots=np.tile(np.arange(8),s); base=np.array([.05,.1,.22,.5,1,2.2,5.5,14])*AU; scale=10**rng.uniform(-.25,.25,s); axes=base[slots]*scale[ps]*rng.uniform(.88,1.12,len(pidx)); pos[sl],vel[sl]=_circular(rng,G*sm[ps],axes); pm=10**rng.uniform(np.log10(.02),np.log10(300),len(pidx))*EARTH_MASS; mass[sl]=pm; rad[sl]=EARTH_RADIUS*np.clip((pm/EARTH_MASS)**.28,.25,14)
    sl=alloc("moons",cnt["moons"],TypeEntiteCatalogue.SATELLITE_NATUREL); midx=np.arange(sl.start,sl.stop); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.ANALYTIC]; hosts=np.concatenate((np.repeat(pidx,2),np.array([pidx[i*8+r] for i in range(s) for r in (2,3,4,5)],np.int64))); rng.shuffle(hosts); hosts=hosts[:len(midx)]; parent[sl]=hosts; fi[sl]=fi[hosts]; hlocal=hosts-pidx[0]; hm=mass[hosts]; hr=rad[hosts]; hs=fi[hosts]; hill=axes[hlocal]*(hm/(3*sm[hs]))**(1/3); mr=np.minimum(hill*rng.uniform(.03,.22,len(midx)),hr*rng.uniform(5,80,len(midx))); mr=np.maximum(mr,hr*2.2); mr=np.minimum(mr,np.maximum(hr*2.2,hill*.25)); rp,rv=_circular(rng,G*hm,mr); pos[sl]=pos[hosts]+rp; vel[sl]=vel[hosts]+rv; mm=np.minimum(hm*.05,10**rng.uniform(15,23,len(midx))); mass[sl]=mm; rad[sl]=np.clip((mm/3000*3/(4*pi))**(1/3),10,4e6)
    sl=alloc("asteroids",cnt["asteroids"],TypeEntiteCatalogue.ASTEROIDE); ai=np.arange(sl.start,sl.stop); asi=np.arange(len(ai),dtype=np.int32)%s; rng.shuffle(asi); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; fi[sl]=asi; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.TRACER]; u=rng.random(len(ai)); ar=np.where(u<.65,rng.uniform(1.8,4.2,len(ai))*AU,np.where(u<.9,rng.uniform(20,80,len(ai))*AU,rng.uniform(.4,1.6,len(ai))*AU)); pos[sl],vel[sl]=_circular(rng,G*sm[asi],ar); mass[sl]=10**rng.uniform(6,19,len(ai)); rad[sl]=np.clip((mass[sl]/2500*3/(4*pi))**(1/3),.1,5e5)
    sl=alloc("comets",cnt["comets"],TypeEntiteCatalogue.COMETE); ci=np.arange(sl.start,sl.stop); csi=np.arange(len(ci),dtype=np.int32)%s; rng.shuffle(csi); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; fi[sl]=csi; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.TRACER]; cr=rng.uniform(20,120,len(ci))*AU; e=rng.uniform(.55,.97,len(ci)); aa=cr/(1+e); cp,cv=_circular(rng,G*sm[csi],cr); circ=np.linalg.norm(cv,axis=1); vis=np.sqrt(np.maximum(G*sm[csi]*(2/cr-1/aa),0)); cv*=np.divide(vis,circ,out=np.zeros_like(vis),where=circ>0)[:,None]; pos[sl]=cp; vel[sl]=cv; mass[sl]=10**rng.uniform(8,17,len(ci)); rad[sl]=np.clip((mass[sl]/600*3/(4*pi))**(1/3),1,1e5)
    sl=alloc("debris",cnt["debris"],TypeEntiteCatalogue.DEBRIS_ARTIFICIEL); di=np.arange(sl.start,sl.stop); dsi=np.arange(len(di),dtype=np.int32)%s; rng.shuffle(dsi); fk[sl]=TypeCadreCatalogue.SYSTEME_STELLAIRE; fi[sl]=dsi; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.VISUAL_ONLY]; dr=10**rng.uniform(np.log10(.01*AU),np.log10(5*AU),len(di)); pos[sl],vel[sl]=_circular(rng,G*sm[dsi],dr); vel[sl]*=rng.uniform(.85,1.15,len(di))[:,None]; mass[sl]=10**rng.uniform(-2,5,len(di)); rad[sl]=10**rng.uniform(-2,1.5,len(di))
    sl=alloc("ships",cnt["ships"],TypeEntiteCatalogue.VEHICULE_SR); ship=np.arange(sl.start,sl.stop); n=len(ship); fk[sl]=TypeCadreCatalogue.GROUPE_GALACTIQUE; fi[sl]=-1; act[sl]=_NIVEAU_CODE[NiveauActiviteCalcul.ACTIVE]; origin=rng.integers(0,s,n,dtype=np.int32); og=sg[origin]; start=gpos[og]+spos[origin]; inter=(rng.random(n)<.16) if g>1 else np.zeros(n,dtype=bool); target_sys=rng.integers(0,s,n,dtype=np.int32); tg=sg[target_sys].copy(); target=gpos[tg]+spos[target_sys]
    if inter.any():
        chosen=(og[inter]+rng.integers(1,g,inter.sum()))%g; target[inter]=gpos[chosen]; tg[inter]=chosen; target_sys[inter]=-1
    direction=target-start; dn=np.linalg.norm(direction,axis=1); zero=dn<1
    if zero.any(): direction[zero]=_unit(rng,zero.sum()); dn=np.linalg.norm(direction,axis=1)
    direction/=dn[:,None]; perm=rng.permutation(n); a,b,cc=int(.25*n),int(.35*n),int(.30*n); beta=np.empty(n); beta[perm[:a]]=rng.uniform(.01,.2,a); beta[perm[a:a+b]]=rng.uniform(.2,.8,b); beta[perm[a+b:a+b+cc]]=rng.uniform(.8,.99,cc); beta[perm[a+b+cc:]]=rng.uniform(.99,.999999,n-a-b-cc); vv=direction*(beta*C)[:,None]; vm=10**rng.uniform(3,9,n); gamma=1/np.sqrt(1-beta*beta); mom=vv*(gamma*vm)[:,None]; pos[sl]=start; vel[sl]=vv; mass[sl]=vm; rad[sl]=10**rng.uniform(0,2.5,n)
    modes=rng.choice(np.array([0,1,2,3],np.int8),size=n,p=[.2,.25,.45,.1]); eta=np.arctanh(beta); req=rng.uniform(.01,.35,n); delta=np.where(np.isin(modes,(2,3)),np.minimum(req,np.maximum(1e-6,.45*eta)),req); fa=rng.uniform(.01,.04,n); fd=rng.uniform(.01,.04,n)
    if cursor!=N or not all(np.isfinite(x).all() for x in (pos,vel,mass,rad)) or np.any(np.linalg.norm(vel[sl],axis=1)>=C): raise ArithmeticError("Invalid generated catalogue")
    return CatalogueMultiGalaxies(c,slices,morph,gpos,gv,gm,gr,sg,spos,sv,typ,fk,fi,parent,pos,vel,mass,rad,act,mom,beta,origin,target_sys,tg,modes,delta,fa,fd)
