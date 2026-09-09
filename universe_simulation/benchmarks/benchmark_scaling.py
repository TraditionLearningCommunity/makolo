#!/usr/bin/env python3
"""Reproducible gravity-scaling benchmark with a timeout per population size."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
import resource
import time

import numpy as np

from universe_sim.gravity import NUMBA_DISPONIBLE, SolveurGraviteBarnesHutCompile, SolveurGraviteDirect


def _relative_errors(approx: np.ndarray, exact: np.ndarray) -> np.ndarray:
    denominator = np.maximum(np.linalg.norm(exact, axis=1), 1e-300)
    return np.linalg.norm(approx - exact, axis=1) / denominator


def _worker(size: int, seed: int, theta: float, leaf_capacity: int, softening_m: float, max_direct: int, queue) -> None:
    rng = np.random.default_rng(seed + size)
    positions = rng.uniform(-5e20, 5e20, size=(size, 3))
    masses = 10 ** rng.uniform(20, 30, size=size)
    solver = SolveurGraviteBarnesHutCompile(theta=theta, leaf_capacity=leaf_capacity, softening_m=softening_m)
    solver.accelerations(positions[: min(size, 128)], masses[: min(size, 128)])
    start = time.perf_counter()
    approximate = solver.accelerations(positions, masses)
    elapsed = time.perf_counter() - start
    result = {
        "n": size,
        "status": "ok",
        "solver": solver.nom,
        "theta": theta,
        "leaf_capacity": leaf_capacity,
        "elapsed_s": elapsed,
        "bodies_per_s": size / elapsed,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        "finite": bool(np.all(np.isfinite(approximate))),
    }
    if size <= max_direct:
        exact = SolveurGraviteDirect(block_size=256, softening_m=softening_m).accelerations(positions, masses)
        error = _relative_errors(approximate, exact)
        result.update(
            error_median=float(np.median(error)),
            error_p95=float(np.quantile(error, .95)),
            error_max=float(np.max(error)),
        )
    queue.put(result)


def run_one(size: int, args) -> dict[str, object]:
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_worker,
        args=(size, args.seed, args.theta, args.leaf_capacity, args.softening_m, args.max_direct, queue),
    )
    process.start()
    process.join(args.timeout)
    if process.is_alive():
        process.terminate()
        process.join()
        return {"n": size, "status": "timeout", "timeout_s": args.timeout}
    if process.exitcode != 0:
        return {"n": size, "status": "error", "exitcode": process.exitcode}
    if queue.empty():
        return {"n": size, "status": "error", "reason": "worker produced no result"}
    return queue.get()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[1_000, 10_000, 100_000, 500_000, 1_000_000])
    parser.add_argument("--timeout", type=float, default=60.0, help="timeout per size, seconds")
    parser.add_argument("--theta", type=float, default=.8)
    parser.add_argument("--leaf-capacity", type=int, default=48)
    parser.add_argument("--softening-m", type=float, default=1e8)
    parser.add_argument("--max-direct", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--output", type=Path, default=Path("benchmark_scaling.json"))
    args = parser.parse_args()
    if not NUMBA_DISPONIBLE:
        raise SystemExit("Install the performance extra: pip install -e '.[performance]'")
    results = []
    for size in args.sizes:
        result = run_one(size, args)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    payload = {
        "configuration": {
            "theta": args.theta,
            "leaf_capacity": args.leaf_capacity,
            "softening_m": args.softening_m,
            "timeout_s": args.timeout,
            "seed": args.seed,
        },
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
