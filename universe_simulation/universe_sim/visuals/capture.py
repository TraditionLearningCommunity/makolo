"""Capture simulation states without coupling renderers to the physics engine."""
from __future__ import annotations

from .models import CorpsVisuel, FrameVisuelle, SequenceVisuelle
from ..simulation import Simulation


def _capturer_frame(simulation: Simulation) -> FrameVisuelle:
    positions = {}
    for corps in simulation.univers.corps_physiques:
        position = corps.etat().position()
        if position is not None:
            positions[corps.id] = position
    return FrameVisuelle(simulation.horloge.instant_courant.seconds, positions)


def capturer_sequence(
    simulation: Simulation,
    pas_total: int,
    frames: int = 180,
) -> SequenceVisuelle:
    """Advance the simulation and sample an exact number of physical steps.

    The first frame is the initial state and the last one is exactly the state
    reached after ``pas_total`` simulation steps. No renderer changes physics.
    ``EtatPhysique.position()`` keeps capture independent from the selected
    classical, SR or curved-space-time kinematics.
    """
    if pas_total < 0:
        raise ValueError("pas_total must be non-negative")
    if frames < 1:
        raise ValueError("frames must be at least 1")

    corps_visuels = tuple(
        CorpsVisuel(
            id=corps.id,
            nom=corps.nom,
            type_corps=type(corps).__name__,
            rayon_m=None if corps.rayon_reference is None else corps.rayon_reference.value,
            masse_kg=None if corps.etat().massique is None else corps.masse().value,
        )
        for corps in simulation.univers.corps_physiques
    )

    if pas_total == 0:
        return SequenceVisuelle(
            simulation.univers.nom,
            corps_visuels,
            (_capturer_frame(simulation),),
            0,
        )

    nombre_frames = min(max(2, frames), pas_total + 1)
    cibles = [round(i * pas_total / (nombre_frames - 1)) for i in range(nombre_frames)]
    captures = []
    pas_courant = 0
    for cible in cibles:
        while pas_courant < cible:
            simulation.avancer()
            pas_courant += 1
        captures.append(_capturer_frame(simulation))

    return SequenceVisuelle(
        simulation.univers.nom,
        corps_visuels,
        tuple(captures),
        pas_total,
    )
