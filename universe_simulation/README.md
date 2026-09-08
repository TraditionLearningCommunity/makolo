# Universe Simulation

Standalone Python implementation of the V2.3 dynamic physical-universe model, isolated from the Django application in the repository root.

The package deliberately keeps physical vocabulary and SI units: `Univers`, `CorpsPhysique`, `Etoile`, `Planete`, `SatelliteNaturel`, `TrouNoir`, `Vehicule`, `Constellation`, `ChampPhysique`, `InteractionPhysique`, `Force`, etc. Real objects such as the Sun, Earth and Moon can be instantiated directly; algorithmic abstractions can be derived later without contaminating the physical reference model.

## Design rules

- Bodies own physical properties and an instantaneous `EtatPhysique`, not their future trajectory.
- Position and velocity belong to the state and are expressed in a `Referentiel`.
- Mass, charge and other simple quantities are typed value objects, not MCD entities.
- Systems are not bodies; systems may be nested without forcing a strict tree.
- Constellations and asterisms are observational structures, not gravitational systems.
- Orbit, barycenter, Lagrange points and Hill spheres are derived physical structures.
- Interactions, laws/models and effects (`Force`, `Couple`, `Impulsion`, `VariationMasse`) are separate concepts.
- Multi-object calculations are external services.
- The universe model is separate from the simulation engine.
- Relativity is kept as a geometry/worldline extension rather than being forced into `F = ma`.

## Structure

```text
universe_simulation/
  main.py
  universe_sim/
    values.py
    spacetime.py
    states.py
    bodies.py
    systems.py
    observation.py
    derived.py
    fields.py
    interactions.py
    effects.py
    events.py
    relativity.py
    laws/
    services/
    simulation/
    examples/
    visualization.py
  tests/
```

## Quick start

```bash
cd universe_simulation
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py --days 30 --dt 3600
```

Animate the physically scaled Sun-Earth-Moon example:

```bash
python main.py --days 30 --dt 3600 --show
```

Save a GIF:

```bash
python main.py --days 30 --dt 3600 --save universe.gif
```

Use the symplectic integrator for conservative orbital simulations:

```bash
python main.py --days 365.25 --dt 21600 --integrator symplectic
```

Focus on Earth to inspect the Moon on a smaller spatial scale:

```bash
python main.py --days 30 --dt 1800 --show --focus Terre --span-au 0.004
```

Marker sizes in the visualization are illustrative; positions, velocities, masses and dynamics remain in physical SI scale.

## Programmatic use

```python
from universe_sim.examples import construire_systeme_solaire_minimal
from universe_sim.constants import DAY

sim = construire_systeme_solaire_minimal(dt=3600.0)
sim.executer(10 * DAY)
terre = sim.univers.trouver_corps("Terre")
print(terre.etat().translation.position)
print(sim.diagnostic())
```

## Implemented physics

- Newtonian point-mass N-body gravity
- optional J2 correction
- classical Lorentz force in prescribed E/B fields
- atmospheric quadratic drag
- radiation pressure
- prescribed physical thrust plus mass flow
- spherical collision-event detection
- frame transformations with translation/rotation transport terms
- barycenter, energies, linear and angular momentum
- state ↔ Keplerian orbital elements
- orbital period, escape speed, Hill sphere and sphere of influence
- approximate L1-L5 positions
- zero-revolution universal-variable Lambert solver
- apparent observation with first-order light-time correction
- constellation-region lookup
- Schwarzschild radius/metric helpers, gravitational redshift and Hawking temperature
- Euler, RK4 and velocity-Verlet/symplectic evolution
- conservation diagnostics, snapshots and history
- Matplotlib animation and GIF export

The GR classes intentionally do not emit a Newtonian force. A future geodesic/worldline integrator is the correct extension for fully relativistic trajectory evolution.

## Tests

```bash
python -m unittest discover -s tests -v
```
