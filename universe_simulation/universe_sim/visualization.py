from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from .constants import AU
from .simulation import Simulation

def animer_simulation(simulation:Simulation,frames:int=240,steps_per_frame:int=1,interval_ms:int=30,span:float|None=1.25*AU,focus:str|None=None,save:str|None=None,show:bool=True)->None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation,PillowWriter
    except ImportError as exc:raise RuntimeError("Visualization requires matplotlib. Run: pip install -r requirements.txt") from exc
    fig,ax=plt.subplots(figsize=(8,8));ax.set_aspect("equal",adjustable="box");ax.set_xlabel("x [m]");ax.set_ylabel("y [m]");trails=defaultdict(list);lines={};points={}
    for body in simulation.univers.corps_physiques:
        line,=ax.plot([],[],linewidth=1,alpha=.55,label=f"{body.nom} trajectory");point,=ax.plot([],[],marker="o",linestyle="None",markersize=8,label=body.nom);lines[body.id]=line;points[body.id]=point
    if span is not None:ax.set_xlim(-span,span);ax.set_ylim(-span,span)
    ax.legend(loc="upper right",fontsize=8)
    def center():
        if focus is None:return 0.,0.
        position=simulation.univers.trouver_corps(focus).etat().position();return (0.,0.) if position is None else (position.x,position.y)
    def update(_frame):
        for _ in range(steps_per_frame):simulation.avancer()
        cx,cy=center()
        for body in simulation.univers.corps_physiques:
            position=body.etat().position()
            if position is None:continue
            trails[body.id].append((position.x-cx,position.y-cy));lines[body.id].set_data([p[0] for p in trails[body.id]],[p[1] for p in trails[body.id]]);points[body.id].set_data([position.x-cx],[position.y-cy])
        if span is None:ax.relim();ax.autoscale_view()
        else:ax.set_xlim(-span,span);ax.set_ylim(-span,span)
        ax.set_title(f"{simulation.univers.nom} - t = {simulation.horloge.instant_courant.seconds/86400:.2f} days");return [*lines.values(),*points.values()]
    animation=FuncAnimation(fig,update,frames=frames,interval=interval_ms,blit=False,repeat=False)
    if save:
        path=Path(save)
        if path.suffix.lower()!=".gif":raise ValueError("The built-in portable writer currently saves GIF files")
        animation.save(path,writer=PillowWriter(fps=max(1,int(1000/interval_ms))))
    if show:plt.show()
    else:plt.close(fig)
