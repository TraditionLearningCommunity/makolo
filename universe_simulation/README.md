# Makolo Universe Simulator

A standalone Python module for representing a physical universe, evolving its
state through time, and observing the result as animated 2D/3D sequences.

This directory is independent from the Django application that also lives in
the Makolo repository.

## Design rule

The visualization layer does not decide how bodies move.

```text
physical entities + current state
            |
            v
     physical models
            |
            v
      state derivatives
            |
            v
    numerical integrator
            |
            v
       state(t + dt)
            |
            v
   visual frame capture
            |
            +--> Matplotlib 2D
            +--> Plotly interactive 3D
            +--> PyVista cinematic 3D
```

A camera can zoom, orbit or follow a body. Rendered sphere radii may be
exaggerated so that planets remain visible across astronomical distances, but
positions and trajectories come from the physical state produced by the
simulation engine.

## What changed in v0.2

- More physical demonstration scenes.
- Multi-scale astronomical camera presets.
- 3D animated Plotly renderer with play/pause, timeline and hover data.
- 3D cinematic PyVista/VTK renderer with moving camera and trails.
- GIF and MP4 export through PyVista.
- Self-contained animated HTML export through Plotly.
- A camera tour that moves from Solar-System scale to inner-system scale and
  then to an Earth-Moon close view when those bodies are present.
- Visual frame capture separated from the physics engine.

No gravity, integration, collision or other physics algorithm is changed by
this visualization work.

## Available scenes

Run:

```bash
python main.py --list-scenes
```

The current scenes are:

| Scene | Content | Default view |
| --- | --- | --- |
| `minimal` | Sun, Earth, Moon | Inner system |
| `inner` | Sun, Mercury, Venus, Earth, Moon, Mars | Inner system |
| `solar` | Sun, eight planets, Moon | Multi-scale cinematic tour |
| `earth-moon` | Earth-Moon barycentric two-body system | Earth-Moon |
| `binary` | Two stars around their barycenter | Binary-star view |

The expanded Solar-System scenes use nominal masses, radii and orbital scales
for reproducible demonstrations. Planetary initial conditions are intentionally
circularized and are not intended to replace a JPL/NASA ephemeris.

## Installation

### Everything used by the demos

```bash
cd universe_simulation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the virtual environment with the corresponding
`.venv\\Scripts\\activate` command.

### Optional extras

Base package only:

```bash
pip install -e .
```

Interactive browser 3D:

```bash
pip install -e ".[interactive]"
```

Cinematic 3D and movie export:

```bash
pip install -e ".[cinematic]"
```

All visual renderers:

```bash
pip install -e ".[all]"
```

## Interactive 3D with Plotly

Open the complete Solar System in an interactive browser view:

```bash
python main.py \
  --scene solar \
  --renderer plotly \
  --days 365 \
  --frames 180 \
  --camera tour \
  --show
```

The result has play/pause controls, a time slider, 3D orbit controls and body
hover information.

Export a self-contained HTML animation:

```bash
python main.py \
  --scene solar \
  --renderer plotly \
  --days 365 \
  --frames 180 \
  --camera orbit \
  --save solar-system.html
```

## Cinematic 3D with PyVista

Render an MP4 sequence with real 3D spheres, trails and a moving camera:

```bash
python main.py \
  --scene solar \
  --renderer pyvista \
  --days 365 \
  --frames 240 \
  --camera tour \
  --save solar-tour.mp4
```

Render a GIF instead:

```bash
python main.py \
  --scene earth-moon \
  --renderer pyvista \
  --days 30 \
  --frames 180 \
  --camera orbit \
  --save earth-moon.gif
```

Open a live PyVista window:

```bash
python main.py \
  --scene binary \
  --renderer pyvista \
  --camera orbit \
  --show
```

## Multi-scale views

Available scale presets:

```text
auto
solar
inner
earth-moon
earth-orbit
binary
```

Examples:

```bash
python main.py --scene solar --renderer plotly --scale solar --camera orbit --show
python main.py --scene inner --renderer plotly --scale inner --camera orbit --show
python main.py --scene earth-moon --renderer pyvista --scale earth-moon --focus Terre --camera orbit --show
```

For normal camera modes:

- `static`: fixed camera.
- `follow`: fixed view direction, center follows the selected body.
- `orbit`: camera circles while following the selected center.
- `tour`: cinematic multi-scale path. On the full Solar-System scene it moves
  from the outer system to the inner system and then toward Earth-Moon scale.

The camera transition uses logarithmic interpolation for view span. This is a
presentation technique only; it does not rescale the physical state.

## Automatic renderer selection

`--renderer auto` is the default.

- `--show` without an export selects Plotly.
- `.html` selects Plotly.
- `.gif` or `.mp4` selects PyVista.
- With no visual request, the program runs the simulation and prints physical
  diagnostics.

For example:

```bash
python main.py --scene solar --show
python main.py --scene solar --save solar.html
python main.py --scene solar --save solar.mp4
```

## Existing 2D renderer

The original Matplotlib renderer remains available:

```bash
python main.py \
  --scene minimal \
  --renderer 2d \
  --days 30 \
  --show
```

It remains useful as a simple debugging and compatibility view.

## Directory structure

```text
universe_simulation/
|-- main.py
|-- requirements.txt
|-- pyproject.toml
|-- universe_sim/
|   |-- bodies.py
|   |-- states.py
|   |-- systems.py
|   |-- laws/
|   |-- services/
|   |-- simulation/
|   |-- examples/
|   |   |-- solar_system.py
|   |   |-- catalogue.py
|   |   `-- scenes.py
|   |-- visuals/
|   |   |-- models.py
|   |   |-- capture.py
|   |   |-- scales.py
|   |   |-- camera.py
|   |   |-- style.py
|   |   |-- plotly3d.py
|   |   `-- pyvista3d.py
|   `-- visualization.py
`-- tests/
```

## Visual architecture

`capturer_sequence()` is the boundary between physics and rendering. It stores
sampled positions from the already-running simulation in renderer-neutral
frames. Plotly and PyVista receive the same `SequenceVisuelle`.

This is important because it means changing a color, camera path, zoom level,
frame rate, sphere size or renderer cannot change gravity or orbital dynamics.

## About astronomical scale

A real Solar-System render has an unavoidable visibility problem: if one AU is
shown at screen scale, the physical radius of a terrestrial planet becomes a
nearly invisible pixel. The renderers therefore separate:

1. physical position, always taken from the simulator;
2. physical radius, kept as body metadata;
3. displayed sphere radius, adapted to the current camera span.

The UI explicitly labels rendered radii as visually exaggerated.

## Visualization libraries

The project uses:

- Matplotlib for the lightweight legacy 2D animation;
- Plotly for portable interactive 3D HTML animation;
- PyVista/VTK for scientific 3D rendering, camera animation and GIF/MP4 movie
  output.

Official references:

- https://plotly.com/python/animations/
- https://plotly.com/python/3d-scatter-plots/
- https://docs.pyvista.org/examples/02-plot/gif.html
- https://docs.pyvista.org/examples/02-plot/movie.html
- https://docs.pyvista.org/examples/03-widgets/animation.html

## Tests

Run:

```bash
python -m unittest discover -s tests
```

The visualization tests intentionally avoid importing Plotly or PyVista. They
validate scene construction, frame capture and camera planning separately so
the physics/visual boundary can be tested even on headless environments.
