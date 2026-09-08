"""Interactive 3D animation rendered with Plotly."""
from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path
from random import Random

from .camera import EtatCamera, construire_plan_camera
from .models import SequenceVisuelle
from .scales import EchelleVue
from .style import style_corps


def _camera_plotly(etat: EtatCamera) -> dict[str, object]:
    azimut = radians(etat.azimut_deg)
    elevation = radians(etat.elevation_deg)
    distance = 1.85
    return {
        "eye": {
            "x": distance * cos(elevation) * cos(azimut),
            "y": distance * cos(elevation) * sin(azimut),
            "z": distance * sin(elevation),
        },
        "up": {"x": 0.0, "y": 0.0, "z": 1.0},
    }


def _scene_layout(etat: EtatCamera, unite_m: float, unite_label: str) -> dict[str, object]:
    cx, cy, cz = (value / unite_m for value in etat.centre.as_tuple())
    span = etat.span_m / unite_m
    axis = lambda centre: {
        "range": [centre - span, centre + span],
        "visible": False,
        "showgrid": False,
        "zeroline": False,
        "showbackground": False,
        "title": "",
    }
    return {
        "xaxis": axis(cx),
        "yaxis": axis(cy),
        "zaxis": axis(cz),
        "aspectmode": "cube",
        "camera": _camera_plotly(etat),
        "bgcolor": "#02040A",
    }


def _etoiles_normales(nombre: int = 160) -> tuple[tuple[float, float, float], ...]:
    rng = Random(9)
    resultats = []
    while len(resultats) < nombre:
        x, y, z = (rng.uniform(-1.0, 1.0) for _ in range(3))
        norme = (x * x + y * y + z * z) ** 0.5
        if norme < 0.65 or norme > 1.0:
            continue
        resultats.append((x / norme, y / norme, z / norme))
    return tuple(resultats)


def _trace_etoiles(go, camera: EtatCamera, unite_m: float, normales) -> object:
    centre = camera.centre
    rayon = camera.span_m * 0.96
    x, y, z = [], [], []
    for nx, ny, nz in normales:
        x.append((centre.x + nx * rayon) / unite_m)
        y.append((centre.y + ny * rayon) / unite_m)
        z.append((centre.z + nz * rayon) / unite_m)
    return go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="markers",
        marker={"size": 1.4, "color": "#DCE7FF", "opacity": 0.55},
        hoverinfo="skip",
        showlegend=False,
        name="Background stars",
    )


def _traces_frame(go, sequence: SequenceVisuelle, index: int, camera: EtatCamera, echelle: EchelleVue, trail_points: int, normales) -> list[object]:
    traces = [_trace_etoiles(go, camera, echelle.unite_m, normales)]
    frame = sequence.frames[index]
    debut = max(0, index - max(1, trail_points) + 1)
    corps_par_id = sequence.corps_par_id()

    for corps_id, corps in corps_par_id.items():
        style = style_corps(corps)
        trajectoire = [f.positions[corps_id] for f in sequence.frames[debut : index + 1] if corps_id in f.positions]
        traces.append(
            go.Scatter3d(
                x=[p.x / echelle.unite_m for p in trajectoire],
                y=[p.y / echelle.unite_m for p in trajectoire],
                z=[p.z / echelle.unite_m for p in trajectoire],
                mode="lines",
                line={"color": style.couleur, "width": 2},
                opacity=0.42,
                hoverinfo="skip",
                showlegend=False,
                name=f"{corps.nom} trail",
            )
        )
        position = frame.positions.get(corps_id)
        if position is None:
            traces.append(go.Scatter3d(x=[], y=[], z=[], mode="markers", showlegend=False))
            continue
        masse = "n/a" if corps.masse_kg is None else f"{corps.masse_kg:.3e} kg"
        traces.append(
            go.Scatter3d(
                x=[position.x / echelle.unite_m],
                y=[position.y / echelle.unite_m],
                z=[position.z / echelle.unite_m],
                mode="markers+text" if corps.type_corps == "Etoile" else "markers",
                text=[corps.nom] if corps.type_corps == "Etoile" else None,
                textposition="top center",
                marker={
                    "size": style.taille_point,
                    "color": style.couleur,
                    "opacity": 0.98,
                    "line": {"width": 0.7, "color": "#FFFFFF"},
                },
                customdata=[[corps.nom, corps.type_corps, masse]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Type: %{customdata[1]}<br>"
                    "Mass: %{customdata[2]}<br>"
                    f"x=%{{x:.6g}} {echelle.unite_label}<br>"
                    f"y=%{{y:.6g}} {echelle.unite_label}<br>"
                    f"z=%{{z:.6g}} {echelle.unite_label}<extra></extra>"
                ),
                name=corps.nom,
                showlegend=True,
            )
        )
    return traces


def rendre_plotly_3d(
    sequence: SequenceVisuelle,
    echelle: EchelleVue,
    focus: str | None = None,
    camera: str = "orbit",
    trail_points: int = 120,
    interval_ms: int = 45,
    save: str | None = None,
    show: bool = True,
):
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise RuntimeError("Plotly 3D requires plotly. Install the interactive visualization extra.") from exc

    if not sequence.frames:
        raise ValueError("Cannot render an empty visual sequence")

    plan = construire_plan_camera(sequence, echelle, focus, camera)
    normales = _etoiles_normales()
    donnees_initiales = _traces_frame(go, sequence, 0, plan[0], echelle, trail_points, normales)
    frames_plotly = []
    indices = list(range(len(donnees_initiales)))
    for index, frame in enumerate(sequence.frames):
        frames_plotly.append(
            go.Frame(
                name=str(index),
                data=_traces_frame(go, sequence, index, plan[index], echelle, trail_points, normales),
                traces=indices,
                layout={"scene": _scene_layout(plan[index], echelle.unite_m, echelle.unite_label)},
            )
        )

    fig = go.Figure(data=donnees_initiales, frames=frames_plotly)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#02040A",
        plot_bgcolor="#02040A",
        title={"text": f"{sequence.univers_nom} - 3D physical simulation", "x": 0.5},
        scene=_scene_layout(plan[0], echelle.unite_m, echelle.unite_label),
        margin={"l": 0, "r": 0, "t": 55, "b": 0},
        legend={"x": 0.01, "y": 0.99, "bgcolor": "rgba(0,0,0,0.25)"},
        annotations=[{"text": f"Display unit: {echelle.unite_label} - body radii visually exaggerated", "showarrow": False, "x": 0.01, "y": 0.01, "xref": "paper", "yref": "paper", "font": {"size": 10, "color": "#8B98B8"}}],
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0.02,
                "y": 0.04,
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [None, {"frame": {"duration": interval_ms, "redraw": True}, "transition": {"duration": 0}, "fromcurrent": True}],
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "x": 0.16,
                "len": 0.80,
                "y": 0.03,
                "currentvalue": {"prefix": "t = "},
                "steps": [
                    {
                        "label": f"{frame.instant_s / 86400.0:.1f} d",
                        "method": "animate",
                        "args": [[str(i)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
                    }
                    for i, frame in enumerate(sequence.frames)
                ],
            }
        ],
    )

    if save:
        path = Path(save)
        if path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("Plotly animation is exported as HTML. Use a .html file.")
        fig.write_html(str(path), include_plotlyjs=True, auto_play=False)
    if show:
        fig.show()
    return fig
