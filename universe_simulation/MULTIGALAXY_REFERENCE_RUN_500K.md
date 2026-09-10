# Multi-galaxy 500k reference run

Date: 2026-09-10

This note records the large-scale numerical reference run used while implementing the multi-galaxy scenario. It is intentionally distinguished from a runtime validation of the newly committed hybrid SR-to-GR runner.

## Reference configuration

- Catalogue size: 500,000 physical catalogue entries.
- Galaxies: 10.
- Stellar systems: 2,400.
- Special-relativistic vehicles: 5,000.
- Coordinate-time duration: 5,000,000 Julian years.
- SR coordinate-time step: 500 years.
- Galaxy aggregate step: 5,000 years.
- SR steps: 10,000.
- Galaxy aggregate steps: 1,000.

### Catalogue composition

| Category | Count |
| --- | ---: |
| Central black holes | 10 |
| Stars | 2,760 |
| Planets | 19,200 |
| Natural satellites | 48,000 |
| Asteroids | 383,030 |
| Comets | 12,000 |
| Artificial debris | 30,000 |
| SR vehicles | 5,000 |
| **Total** | **500,000** |

## Observed reference result

On the implementation environment used for this reference run:

- Compact catalogue generation: about 0.35 s.
- Compact catalogue arrays: about 37.79 MiB before compression.
- Active long-horizon simulation: about 5.39 s.
- Initial beta range: 0.01022 to 0.999966.
- Final beta range: 0.005653 to 0.999980.
- Final median beta: about 0.63978.
- Minimum accumulated proper time: about 31,676 years.
- Median accumulated proper time: about 3,622,116 years.
- Maximum accumulated proper time: about 4,999,740 years.
- Median travelled distance: about 1,056,408 pc.
- 95th percentile travelled distance: about 1,527,554 pc.
- Maximum travelled distance: about 1,532,976 pc.
- Maximum displacement of a galaxy aggregate: about 782.3 pc.

Mission-program counts in this reference realization:

- coast: 1,011;
- early acceleration: 1,229;
- early acceleration plus late deceleration: 2,261;
- late deceleration: 499.

## Physical/numerical interpretation

This is not a 500,000-body direct N-body integration. The catalogue is hierarchical and compact. The long-run active dynamics in this reference execution consisted of:

1. ten Newtonian galaxy aggregate centers evolved with mutual gravity;
2. 5,000 independent special-relativistic vehicle states evolved by canonical momentum `dp/dt`, with velocity derived relativistically and proper time integrated from gamma;
3. the remaining stars, planets, moons, asteroids, comets and debris retained as physical catalogue entries in local galaxy/system frames until their level of detail is opened.

This distinction is essential to the design: physical existence in the conceptual universe does not imply that every entity must participate in the hottest numerical loop at every coordinate-time step.

## Relation to the committed hybrid runner

The branch now contains additional code that was not part of this reference artifact:

- intergalactic arrival-impact diversification;
- continuous black-hole transition-sphere detection;
- local Poincare/Lorentz transformation of vehicle events and four-momenta;
- materialization of selected vehicles and central black holes;
- explicit SR-to-GR numerical-ownership transfer;
- adaptive Schwarzschild/Kerr geodesic evolution;
- horizon-crossing handling;
- hybrid NPZ + GR-worldline persistence;
- `run_multigalaxy.py` CLI for `mini`, `10k`, `100k`, and `500k` runs.

The current execution environment could not clone the complete GitHub branch, so the values above must not be cited as a runtime validation of that new hybrid path. They are a reproducible large-scale reference for the compact catalogue and active Newton/SR equations used during development.
