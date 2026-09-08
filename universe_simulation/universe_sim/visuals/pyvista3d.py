"""Cinematic 3D renderer based on PyVista/VTK."""
from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path
from random import Random

from .camera import EtatCamera, construire_plan_camera
from .models import SequenceVisuelle
from .scales import EchelleVue
from .style import rayon_affichage, style_corps


def _normales_etoiles(nombre: int = 320) -> tuple[tuple[float, float, float], ...]:
    rng = Random(99)
    resultats = []
    while len(resultats) < nombre:
        x, y, z = (rng.uniform(-1.0, 1.0) for _ in range(3))
        norme = (x * x + y * y + z * z) ** 0.5
        if norme < 0.7 or norme > 1.0:
            continue
        resultats.append((x / norme, y / norme, z / norme))
    return tuple(resultats)


def _position_camera(etat: EtatCamera, unite_m: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    centre = tuple(v / unite_m for v in etat.centre.as_tuple())
    azimut = radians(etat.azimut_deg)
    elevation = radians(etat.elevation_deg)
    distance = 2.25 * etat.span_m / unite_m
    direction = (
        cos(elevation) * cos(azimut),
        cos(elevation) * sin(azimut),
        sin(elevation),
    )
    position = tuple(centre[i] + distance * direction[i] for i in range(3))
    return position, centre


def _creer_scene(pv, np, sequence: SequenceVisuelle, echelle: EchelleVue, plan, trail_points: int, off_screen: bool):
    plotter = pv.Plotter(off_screen=off_screen, window_size=(1280, 720))
    plotter.set_background("#02040A")
    try:
        plotter.enable_anti_aliasing("ssaa")
    except Exception:
        pass

    acteurs = {}
    maillages_traces = {}
    for corps in sequence.corps:
        style = style_corps(corps)
        sphere = pv.Sphere(radius=1.0, theta_resolution=48, phi_resolution=32)
        kwargs = {"color": style.couleur, "smooth_shading": True}
        try:
            acteur = plotter.add_mesh(sphere, pbr=True, metallic=0.05, roughness=0.38, **kwargs)
        except TypeError:
            acteur = plotter.add_mesh(sphere, **kwargs)
        acteurs[corps.id] = acteur

        trace = pv.PolyData(np.zeros((2, 3), dtype=float))
        trace.lines = np.array([2, 0, 1], dtype=np.int64)
        maillages_traces[corps.id] = trace
        plotter.add_mesh(trace, color=style.couleur, line_width=1.5, opacity=0.42, lighting=False)

    normales = np.asarray(_normales_etoiles(), dtype=float)
    etoiles = pv.PolyData(np.zeros((len(normales), 3), dtype=float))
    plotter.add_mesh(etoiles, color="#DCE7FF", point_size=2.2, render_points_as_spheres=True, opacity=0.60, lighting=False)
    texte_temps = plotter.add_text("", position="upper_left", font_size=12, color="#DCE7FF", name="simulation-time")
    plotter.add_text("Physical positions - display radii exaggerated", position="lower_left", font_size=9, color="#7C8AA5")

    corps_par_id = sequence.corps_par_id()

    def update(index: int) -> None:
        index = max(0, min(index, len(sequence.frames) - 1))
        frame = sequence.frames[index]
        camera = plan[index]
        unite = echelle.unite_m

        for corps_id, corps in corps_par_id.items():
            position = frame.positions.get(corps_id)
            if position is None:
                continue
            acteur = acteurs[corps_id]
            acteur.position = tuple(v / unite for v in position.as_tuple())
            rayon = rayon_affichage(corps, camera.span_m) / unite
            acteur.scale = (rayon, rayon, rayon)

            debut = max(0, index - max(1, trail_points) + 1)
            points = [
                f.positions[corps_id].as_tuple()
                for f in sequence.frames[debut : index + 1]
                if corps_id in f.positions
            ]
            if len(points) < 2:
                points = points * 2 if points else [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
            pts = np.asarray(points, dtype=float) / unite
            trace = maillages_traces[corps_id]
            trace.points = pts
            trace.lines = np.hstack(([len(pts)], np.arange(len(pts), dtype=np.int64)))

        centre = np.asarray(camera.centre.as_tuple(), dtype=float) / unite
        etoiles.points = centre + normales * (camera.span_m * 0.96 / unite)

        position_camera, focal = _position_camera(camera, unite)
        plotter.camera.position = position_camera
        plotter.camera.focal_point = focal
        plotter.camera.up = (0.0, 0.0, 1.0)
        plotter.camera.clipping_range = (1e-6, max(10.0, 10.0 * camera.span_m / unite))
        texte_temps.SetInput(f"{sequence.univers_nom}   t = {frame.instant_s / 86400.0:.2f} days")
        plotter.render()

    return plotter, update


def _exporter(pv, np, sequence, echelle, plan, trail_points, interval_ms, save):
    plotter, update = _creer_scene(pv, np, sequence, echelle, plan, trail_points, off_screen=True)
    path = Path(save)
    suffix = path.suffix.lower()
    if suffix == ".gif":
        plotter.open_gif(str(path))
    elif suffix == ".mp4":
        fps = max(1, round(1000 / max(1, interval_ms)))
        plotter.open_movie(str(path), framerate=fps)
    else:
        plotter.close()
        raise ValueError("PyVista cinematic export supports .gif or .mp4")
    for index in range(len(sequence.frames)):
        update(index)
        plotter.write_frame()
    plotter.close()


def _afficher(pv, np, sequence, echelle, plan, trail_points, interval_ms):
    plotter, update = _creer_scene(pv, np, sequence, echelle, plan, trail_points, off_screen=False)
    update(0)

    def callback(step: int) -> None:
        update(step)

    plotter.add_timer_event(max_steps=len(sequence.frames), duration=interval_ms, callback=callback)
    plotter.show()


def rendre_pyvista_3d(
    sequence: SequenceVisuelle,
    echelle: EchelleVue,
    focus: str | None = None,
    camera: str = "orbit",
    trail_points: int = 120,
    interval_ms: int = 45,
    save: str | None = None,
    show: bool = True,
) -> None:
    try:
        import numpy as np
        import pyvista as pv
    except ImportError as exc:
        raise RuntimeError("PyVista 3D requires pyvista and numpy. Install the cinematic visualization extra.") from exc

    if not sequence.frames:
        raise ValueError("Cannot render an empty visual sequence")
    plan = construire_plan_camera(sequence, echelle, focus, camera)
    if save:
        _exporter(pv, np, sequence, echelle, plan, trail_points, interval_ms, save)
    if show:
        _afficher(pv, np, sequence, echelle, plan, trail_points, interval_ms)
