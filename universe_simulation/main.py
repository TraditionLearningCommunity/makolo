from __future__ import annotations

import argparse
from pathlib import Path

from universe_sim.constants import AU, DAY
from universe_sim.examples import SCENES, construire_scene
from universe_sim.simulation import IntegrateurEuler, IntegrateurRK4, IntegrateurSymplectique
from universe_sim.visualization import animer_simulation
from universe_sim.visuals import (
    ECHELLES,
    capturer_sequence,
    obtenir_echelle,
    rendre_plotly_3d,
    rendre_pyvista_3d,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Makolo standalone physical-universe simulator")
    parser.add_argument("--scene", choices=tuple(SCENES), default="solar", help="Physical demonstration scene")
    parser.add_argument("--list-scenes", action="store_true", help="List available scenes and exit")
    parser.add_argument("--days", type=float, default=None, help="Physical duration in days; scene default when omitted")
    parser.add_argument("--dt", type=float, default=None, help="Physical time step in seconds; scene default when omitted")
    parser.add_argument("--integrator", choices=("rk4", "symplectic", "euler"), default="symplectic")
    parser.add_argument("--renderer", choices=("auto", "none", "2d", "plotly", "pyvista"), default="auto")
    parser.add_argument("--show", action="store_true", help="Open an interactive animation window/browser")
    parser.add_argument("--save", default=None, help="Export .html (Plotly), .gif/.mp4 (PyVista), or .gif (2D)")
    parser.add_argument("--frames", type=int, default=180, help="Number of sampled visual frames")
    parser.add_argument("--interval-ms", type=int, default=45, help="Playback delay between visual frames")
    parser.add_argument("--trail-points", type=int, default=120, help="Maximum trail samples per body")
    parser.add_argument("--focus", default=None, help="Body name or id followed by the camera")
    parser.add_argument("--scale", choices=tuple(ECHELLES), default=None, help="Visual scale preset")
    parser.add_argument("--camera", choices=("static", "follow", "orbit", "tour"), default=None)
    parser.add_argument("--span-au", type=float, default=1.25, help="Legacy 2D view half-span in AU")
    return parser


def select_integrator(name: str):
    if name == "symplectic":
        return IntegrateurSymplectique()
    if name == "euler":
        return IntegrateurEuler()
    return IntegrateurRK4()


def choisir_renderer(renderer: str, save: str | None, show: bool) -> str:
    if renderer != "auto":
        return renderer
    if save:
        suffix = Path(save).suffix.lower()
        if suffix in {".html", ".htm"}:
            return "plotly"
        if suffix in {".mp4", ".gif"}:
            return "pyvista"
    if show:
        return "plotly"
    return "none"


def afficher_scenes() -> None:
    print("Available scenes:")
    for key, scene in SCENES.items():
        print(
            f"  {key:12s} {scene.description} "
            f"[default {scene.duree_jours_defaut:g} d, dt={scene.dt_defaut:g} s, "
            f"scale={scene.echelle_defaut}, camera={scene.camera_defaut}]"
        )


def afficher_resume(simulation, diagnostic_initial: dict[str, object]) -> None:
    diagnostic_final = simulation.diagnostic()
    print(f"Simulation: {simulation.univers.nom}")
    print(f"Physical time: {simulation.horloge.instant_courant.seconds / DAY:.3f} days")
    print(f"Integrator: {simulation.integrateur.nom}")
    for body in simulation.univers.corps_physiques:
        translation = body.etat().translation
        if translation is None:
            continue
        print(
            f"  - {body.nom:10s} "
            f"p=({translation.position.x:.6e}, {translation.position.y:.6e}, {translation.position.z:.6e}) m "
            f"v=({translation.vitesse.x:.6e}, {translation.vitesse.y:.6e}, {translation.vitesse.z:.6e}) m/s"
        )
    print(f"Initial mechanical energy: {diagnostic_initial['energie_mecanique']:.6e} J")
    print(f"Final mechanical energy:   {diagnostic_final['energie_mecanique']:.6e} J")
    print(f"Relative energy drift:     {diagnostic_final['derive_relative_energie']:.6e}")


def main() -> None:
    args = build_parser().parse_args()
    if args.list_scenes:
        afficher_scenes()
        return

    definition = SCENES[args.scene]
    days = definition.duree_jours_defaut if args.days is None else args.days
    dt = definition.dt_defaut if args.dt is None else args.dt
    if days < 0:
        raise ValueError("--days must be non-negative")
    if dt <= 0:
        raise ValueError("--dt must be positive")

    simulation = construire_scene(args.scene, dt=dt, integrateur=args.integrator)
    simulation.integrateur = select_integrator(args.integrator)
    total_steps = max(0, int(round(days * DAY / dt)))
    renderer = choisir_renderer(args.renderer, args.save, args.show)

    if renderer == "none":
        initial = simulation.diagnostic()
        simulation.executer(days * DAY, dt=dt)
        afficher_resume(simulation, initial)
        print("Use --show for interactive 3D, or --save solar.mp4 / solar.html to export a sequence.")
        return

    if renderer == "2d":
        steps_per_frame = max(1, total_steps // max(1, args.frames)) if total_steps else 1
        actual_frames = max(1, min(args.frames, total_steps + 1 if total_steps else 1))
        animer_simulation(
            simulation,
            frames=actual_frames,
            steps_per_frame=steps_per_frame,
            interval_ms=args.interval_ms,
            span=args.span_au * AU,
            focus=args.focus,
            save=args.save,
            show=args.show,
        )
        return

    sequence = capturer_sequence(simulation, total_steps, frames=args.frames)
    echelle = obtenir_echelle(args.scale or definition.echelle_defaut)
    camera = args.camera or definition.camera_defaut

    if renderer == "plotly":
        rendre_plotly_3d(
            sequence,
            echelle,
            focus=args.focus,
            camera=camera,
            trail_points=args.trail_points,
            interval_ms=args.interval_ms,
            save=args.save,
            show=args.show,
        )
        return

    if renderer == "pyvista":
        rendre_pyvista_3d(
            sequence,
            echelle,
            focus=args.focus,
            camera=camera,
            trail_points=args.trail_points,
            interval_ms=args.interval_ms,
            save=args.save,
            show=args.show,
        )
        return

    raise ValueError(f"Unsupported renderer: {renderer}")


if __name__ == "__main__":
    main()
