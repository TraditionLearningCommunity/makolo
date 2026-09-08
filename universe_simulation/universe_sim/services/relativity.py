from __future__ import annotations
from math import pi,sqrt
from ..constants import C,G
HBAR=1.054571817e-34; K_B=1.380649e-23
def rayon_schwarzschild(masse:float)->float:
    if masse<0: raise ValueError("Mass must be non-negative")
    return 2*G*masse/(C*C)
def metrique_schwarzschild(masse:float,r:float,theta:float):
    rs=rayon_schwarzschild(masse)
    if r<=rs: raise ValueError("Static Schwarzschild coordinates are singular at or inside the horizon")
    from math import sin
    f=1-rs/r
    return ((-f*C*C,0.,0.,0.),(0.,1/f,0.,0.),(0.,0.,r*r,0.),(0.,0.,0.,r*r*sin(theta)**2))
def decalage_gravitationnel_schwarzschild(masse:float,rayon_emission:float,rayon_reception:float=float("inf"))->float:
    rs=rayon_schwarzschild(masse)
    if rayon_emission<=rs: raise ValueError("Emission radius must be outside the horizon")
    return sqrt((1.0 if rayon_reception==float("inf") else 1-rs/rayon_reception)/(1-rs/rayon_emission))-1
def temperature_hawking(masse:float)->float:
    if masse<=0: raise ValueError("Positive mass required")
    return HBAR*C**3/(8*pi*G*masse*K_B)
