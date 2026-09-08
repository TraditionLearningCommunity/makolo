"""External orbital mechanics and astrodynamics services."""
from __future__ import annotations
from math import acos,atan2,cos,pi,sin,sqrt
from ..derived import ElementsOrbitaux,NomPointLagrange
from ..values import Instant,Vecteur3

def etat_vers_elements_orbitaux(r:Vecteur3,v:Vecteur3,mu:float,epoque:Instant)->ElementsOrbitaux:
    if mu<=0: raise ValueError("mu must be positive")
    rmag=r.norm(); vmag2=v.norm2()
    if rmag==0: raise ValueError("Position cannot be zero")
    h=r.cross(v); hmag=h.norm()
    if hmag==0: raise ValueError("Degenerate radial trajectory has no orbital plane")
    k=Vecteur3(0,0,1); n=k.cross(h); nmag=n.norm(); evec=(v.cross(h)/mu)-(r/rmag); e=evec.norm()
    energy=.5*vmag2-mu/rmag; a=float("inf") if abs(energy)<1e-20 else -mu/(2*energy)
    inc=acos(max(-1,min(1,h.z/hmag))); raan=0.0 if nmag==0 else atan2(n.y,n.x)%(2*pi)
    if e<1e-12 or nmag==0: argp=0.0
    else:
        argp=acos(max(-1,min(1,n.dot(evec)/(nmag*e))))
        if evec.z<0: argp=2*pi-argp
    if e<1e-12:
        if nmag==0: nu=atan2(r.y,r.x)%(2*pi)
        else:
            nu=acos(max(-1,min(1,n.dot(r)/(nmag*rmag))))
            if r.dot(v)<0: nu=2*pi-nu
    else:
        nu=acos(max(-1,min(1,evec.dot(r)/(e*rmag))))
        if r.dot(v)<0: nu=2*pi-nu
    return ElementsOrbitaux(a,e,inc,raan,argp,nu,epoque)

def elements_orbitaux_vers_etat(elements:ElementsOrbitaux,mu:float)->tuple[Vecteur3,Vecteur3]:
    a,e,inc=elements.demi_grand_axe,elements.excentricite,elements.inclinaison; O,w,nu=elements.longitude_noeud_ascendant,elements.argument_periastre,elements.anomalie_vraie
    p=a*(1-e*e)
    if p<=0: raise ValueError("This converter currently requires an elliptical orbit with p > 0")
    r_pf=Vecteur3(p*cos(nu)/(1+e*cos(nu)),p*sin(nu)/(1+e*cos(nu)),0); root=sqrt(mu/p); v_pf=Vecteur3(-root*sin(nu),root*(e+cos(nu)),0)
    def rotate(vec:Vecteur3)->Vecteur3:
        cO,sO,cw,sw,ci,si=cos(O),sin(O),cos(w),sin(w),cos(inc),sin(inc)
        m11=cO*cw-sO*sw*ci; m12=-cO*sw-sO*cw*ci; m13=sO*si; m21=sO*cw+cO*sw*ci; m22=-sO*sw+cO*cw*ci; m23=-cO*si; m31=sw*si; m32=cw*si; m33=ci
        return Vecteur3(m11*vec.x+m12*vec.y+m13*vec.z,m21*vec.x+m22*vec.y+m23*vec.z,m31*vec.x+m32*vec.y+m33*vec.z)
    return rotate(r_pf),rotate(v_pf)

def periode_orbitale(a:float,mu:float)->float:
    if a<=0 or mu<=0: raise ValueError("Positive semi-major axis and mu required")
    return 2*pi*sqrt(a**3/mu)
def sphere_hill(a:float,e:float,m2:float,m1:float)->float: return a*(1-e)*(m2/(3*m1))**(1/3)
def sphere_influence(a:float,m2:float,m1:float)->float: return a*(m2/m1)**(2/5)
def point_lagrange_approx(nom:NomPointLagrange,r1:Vecteur3,r2:Vecteur3,m1:float,m2:float)->Vecteur3:
    if m1<=0 or m2<=0: raise ValueError("Positive masses required")
    dvec=r2-r1; d=dvec.norm()
    if d==0: raise ValueError("Distinct primaries required")
    ex=dvec/d; mu=m2/(m1+m2)
    if nom==NomPointLagrange.L1: return r2-ex*(d*(m2/(3*m1))**(1/3))
    if nom==NomPointLagrange.L2: return r2+ex*(d*(m2/(3*m1))**(1/3))
    if nom==NomPointLagrange.L3: return r1-ex*d*(1+5*mu/12)
    ey=Vecteur3(0,0,1).cross(ex).normalized(); midpoint=(r1+r2)*.5; sign=1 if nom==NomPointLagrange.L4 else -1
    return midpoint+ey*(sign*sqrt(3)*d/2)
def _stumpff_c(z:float)->float:
    if z>1e-8:
        s=sqrt(z); return (1-cos(s))/z
    if z<-1e-8:
        from math import cosh
        s=sqrt(-z); return (cosh(s)-1)/(-z)
    return .5-z/24+z*z/720
def _stumpff_s(z:float)->float:
    if z>1e-8:
        s=sqrt(z); return (s-sin(s))/(s**3)
    if z<-1e-8:
        from math import sinh
        s=sqrt(-z); return (sinh(s)-s)/(s**3)
    return 1/6-z/120+z*z/5040
def resoudre_lambert(r1:Vecteur3,r2:Vecteur3,temps_vol:float,mu:float,prograde:bool=True,iterations:int=100)->tuple[Vecteur3,Vecteur3]:
    if temps_vol<=0 or mu<=0: raise ValueError("Positive time of flight and mu required")
    r1m,r2m=r1.norm(),r2.norm(); cos_dt=max(-1,min(1,r1.dot(r2)/(r1m*r2m))); cross_z=r1.cross(r2).z; dtheta=acos(cos_dt)
    if prograde and cross_z<0 or (not prograde and cross_z>=0): dtheta=2*pi-dtheta
    denom=1-cos(dtheta)
    if abs(denom)<1e-14: raise ValueError("Lambert geometry is singular for collinear equal-direction vectors")
    A=sin(dtheta)*sqrt(r1m*r2m/denom)
    if abs(A)<1e-14: raise ValueError("Degenerate Lambert parameter A")
    def tof(z):
        C=_stumpff_c(z); S=_stumpff_s(z)
        if C<=0: return float("inf"),-1
        y=r1m+r2m+A*(z*S-1)/sqrt(C)
        if y<0: return float("inf"),y
        x=sqrt(y/C); return (x**3*S+A*sqrt(y))/sqrt(mu),y
    lo,hi=-4*pi*pi,4*pi*pi
    for _ in range(iterations):
        mid=(lo+hi)/2; tmid,y=tof(mid)
        if y<0 or tmid>temps_vol: hi=mid
        else: lo=mid
    _,y=tof((lo+hi)/2)
    if y<=0: raise RuntimeError("Lambert solver failed to find positive y")
    f=1-y/r1m; g=A*sqrt(y/mu); gdot=1-y/r2m
    if abs(g)<1e-14: raise RuntimeError("Lambert solver produced singular g")
    return (r2-r1*f)/g,(r2*gdot-r1)/g
