"""Reproducible full-connectome smoke run; no server or wallet needed."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frankenfly.brain import Brain
from frankenfly.world import World

parser = argparse.ArgumentParser()
parser.add_argument("--steps", type=int, default=120)
parser.add_argument("--output", type=Path, default=Path("reports/benchmark.json"))
args = parser.parse_args()
brain = Brain(Path("data"))
world = World()
start = time.perf_counter()
durations, movements = [], []
for i in range(args.steps):
    if i == args.steps // 3:
        world.place("shadow", 330, 320)
    if i == args.steps * 2 // 3:
        world.place("odor", 500, 260)
    t = brain.step(world)
    world.move(t["turn"], t["drive"], dt=1/8)
    durations.append(t["compute_ms"])
    movements.append([t["turn"], t["drive"]])
elapsed = time.perf_counter() - start
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform != "darwin":
    peak *= 1024
result = {"neurons": brain.n, "edges": len(brain.data), "steps": args.steps,
          "elapsed_seconds": round(elapsed, 3), "steps_per_wall_second": round(args.steps/elapsed, 2),
          "median_step_ms": round(statistics.median(durations), 1), "peak_rss_mib": round(peak/1024**2, 1),
          "distance_world_units": round(world.distance, 2), "nonzero_motor_steps": sum(any(abs(v) > 0 for v in pair) for pair in movements),
          "graph_sha256": brain.manifest["graph_sha256"], "integration": "12 ms observation windows, reset to rest",
          "note": "Measurements from this execution environment, not a Hetzner load test or a behavioral-learning validation."}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
