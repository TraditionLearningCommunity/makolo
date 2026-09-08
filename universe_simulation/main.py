from __future__ import annotations
import argparse
from universe_sim.constants import AU,DAY
from universe_sim.examples import construire_systeme_solaire_minimal
from universe_sim.simulation import IntegrateurEuler,IntegrateurRK4,IntegrateurSymplectique
from universe_sim.visualization import animer_simulation
def build_parser():
    p=argparse.ArgumentParser(description="Simulate a physically scaled Sun-Earth-Moon universe");p.add_argument("--days",type=float,default=30);p.add_argument("--dt",type=float,default=3600);p.add_argument("--integrator",choices=("rk4","symplectic","euler"),default="rk4");p.add_argument("--show",action="store_true");p.add_argument("--save",default=None);p.add_argument("--frames",type=int,default=240);p.add_argument("--focus",default=None);p.add_argument("--span-au",type=float,default=1.25);return p
def select_integrator(name):
    if name=="symplectic":return IntegrateurSymplectique()
    if name=="euler":return IntegrateurEuler()
    return IntegrateurRK4()
def main():
    args=build_parser().parse_args();simulation=construire_systeme_solaire_minimal(dt=args.dt);simulation.integrateur=select_integrator(args.integrator);total_steps=max(1,int(round(args.days*DAY/args.dt)))
    if args.show or args.save:
        steps_per_frame=max(1,total_steps//max(1,args.frames));actual_frames=max(1,(total_steps+steps_per_frame-1)//steps_per_frame);animer_simulation(simulation,frames=actual_frames,steps_per_frame=steps_per_frame,span=args.span_au*AU,focus=args.focus,save=args.save,show=args.show)
    else:
        initial=simulation.diagnostic();simulation.executer(args.days*DAY,dt=args.dt);final=simulation.diagnostic();print(f"Simulation: {simulation.univers.nom}");print(f"Physical time: {simulation.horloge.instant_courant.seconds/DAY:.3f} days");print(f"Integrator: {simulation.integrateur.nom}")
        for body in simulation.univers.corps_physiques:
            t=body.etat().translation
            if t is not None:print(f"  - {body.nom:8s} p=({t.position.x:.6e}, {t.position.y:.6e}, {t.position.z:.6e}) m v=({t.vitesse.x:.6e}, {t.vitesse.y:.6e}, {t.vitesse.z:.6e}) m/s")
        print(f"Initial mechanical energy: {initial['energie_mecanique']:.6e} J");print(f"Final mechanical energy:   {final['energie_mecanique']:.6e} J");print(f"Relative energy drift:     {final['derive_relative_energie']:.6e}");print("Use --show to animate or --save universe.gif to render a GIF.")
if __name__=="__main__":main()
