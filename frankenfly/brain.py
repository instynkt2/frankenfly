"""Windowed leaky integrate-and-fire simulation of a measured connectome.

Model and motor readout adapted from fruitflydev/flycoinrh (MIT).
Changes: persistent session/RNG state, indexed sensory sampling,
verified graph identity, checkpointing, and a virtual body instead of a browser.
This is an experimental numerical model, not a living or conscious cat/fly.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np


class Brain:
    dt_ms = .2
    rest = -52.
    threshold = -45.
    tau_ms = 20.
    refractory_ms = 2.2

    def __init__(self, directory: Path, seed: int = 42):
        self.directory = directory
        self.manifest = json.loads((directory / "manifest.json").read_text())
        from .prepare import digest
        if digest(directory / "connectome.npz", "sha256") != self.manifest["graph_sha256"]:
            raise ValueError("Connectome checksum mismatch. Rebuild the data.")
        with np.load(directory / "connectome.npz", allow_pickle=False) as z:
            for field in ("data", "indices", "indptr", "bodies", "types", "side", "hex1", "hex2", "xyz"):
                setattr(self, field, z[field].copy())
        self.n = len(self.bodies)
        self.v = np.full(self.n, self.rest, np.float32)
        self.refr = np.zeros(self.n, np.int16)
        self.rng = np.random.default_rng(seed)
        self.total_steps = 0
        self.decay = np.float32(np.exp(-self.dt_ms / self.tau_ms))
        self.refr_steps = int(np.ceil(self.refractory_ms / self.dt_ms))
        self.motor = {
            "left": self.select("DNa02", "L"), "right": self.select("DNa02", "R"),
            "forward": self.select("DNa01"), "reverse": self.select("MDN"),
            "stop": self.select("DNp09"),
        }
        missing = [name for name, indices in self.motor.items() if not len(indices)]
        if missing:
            raise ValueError(f"Missing motor populations: {missing}")
        valid = np.isfinite(self.hex1) & np.isfinite(self.hex2)
        self.on = np.flatnonzero(valid & (self.types == "L1"))
        self.off = np.flatnonzero(valid & (self.types == "L2"))
        both = np.concatenate([self.on, self.off])
        if not len(self.on) or not len(self.off):
            raise ValueError("No retinotopically annotated L1/L2 populations")
        x = self.hex1[both] + .5 * self.hex2[both]
        y = self.hex2[both] * np.sqrt(3) / 2
        self.uv = {}
        for name, indices in (("on", self.on), ("off", self.off)):
            xx = self.hex1[indices] + .5 * self.hex2[indices]
            yy = self.hex2[indices] * np.sqrt(3) / 2
            self.uv[name] = np.column_stack(((xx - x.min()) / max(np.ptp(x), 1), (yy - y.min()) / max(np.ptp(y), 1)))
        # The odor control is an explicitly synthetic pulse into annotated ORNs.
        # It is not a validated banana odor or chemical receptor-response model.
        self.orn = np.flatnonzero(np.char.startswith(self.types.astype(str), "ORN"))
        candidates = np.flatnonzero(np.isfinite(self.xyz).all(axis=1))
        sampler = np.random.default_rng(121)
        self.display = np.sort(sampler.choice(candidates, min(1800, len(candidates)), replace=False))
        self.last_vision = np.empty((0, 3), np.float32)

    def select(self, cell_type, side=None):
        keep = self.types == cell_type
        if side:
            keep &= self.side == side
        return np.flatnonzero(keep)

    def advance(self, input_indices, rates_hz, steps=60):
        """Keep state across calls; spikes propagate along pre -> post edges."""
        probability = np.clip(np.asarray(rates_hz) * self.dt_ms / 1000, 0, 1)
        fired_counts = np.zeros(self.n, np.int32)
        input_indices = np.asarray(input_indices, dtype=np.int32)
        for _ in range(steps):
            self.v = self.rest + (self.v - self.rest) * self.decay
            if len(input_indices):
                hit = input_indices[self.rng.random(len(input_indices)) < probability]
                self.v[hit] = self.threshold + 1
            self.v[self.refr > 0] = self.rest
            fired = np.flatnonzero((self.v >= self.threshold) & (self.refr <= 0))
            if len(fired):
                self.v[fired] = self.rest
                self.refr[fired] = self.refr_steps
                fired_counts[fired] += 1
                starts = self.indptr[fired]
                counts = self.indptr[fired + 1] - starts
                total = int(counts.sum())
                if total:
                    offsets = np.repeat(starts - np.concatenate(([0], np.cumsum(counts)[:-1])), counts)
                    positions = offsets + np.arange(total)
                    # Multiple incoming synapses must sum even for repeated targets.
                    self.v += np.bincount(self.indices[positions], weights=self.data[positions], minlength=self.n).astype(np.float32)
            self.refr = np.maximum(self.refr - 1, 0)
        self.total_steps += steps
        simulated_seconds = steps * self.dt_ms / 1000
        hz = {name: float(fired_counts[indices].mean() / simulated_seconds) for name, indices in self.motor.items()}
        return fired_counts, hz, simulated_seconds

    def step(self, world, steps=60):
        started = time.perf_counter()
        # Match the upstream observation-window scheme. Each frame starts its
        # numerical integration at rest; advance() carries state within a
        # window. This is not a continuous emulation or a memory mechanism.
        # Keeping this simplified network continuously active instead tends to
        # lock its motor readout into silent/saturated states in this arena.
        self.v.fill(self.rest)
        self.refr.fill(0)
        luminance_on = world.sense(self.uv["on"])
        luminance_off = world.sense(self.uv["off"])
        indices = np.concatenate((self.on, self.off))
        rates = np.concatenate((luminance_on * 180, (1 - luminance_off) * 108))
        odor = world.odor_strength()
        if odor > 0 and len(self.orn):
            indices = np.concatenate((indices, self.orn))
            rates = np.concatenate((rates, np.full(len(self.orn), odor * 90)))
        counts, hz, elapsed = self.advance(indices, rates, steps)
        # The transformation into cat motion is an engineered adapter. There
        # is no path planner, target-seeking controller, LLM, or random walk.
        turn = float(np.clip((hz["right"] - hz["left"]) / 450, -1, 1))
        speed = float(np.clip((hz["forward"] - hz["reverse"]) / 450, -1, 1))
        speed *= 1 - float(np.clip(hz["stop"] / 450, 0, 1))
        step_ms = (time.perf_counter() - started) * 1000
        return {
            "turn": turn, "drive": speed, "motor_hz": hz,
            "firing": int(np.count_nonzero(counts)), "spikes": int(counts.sum()),
            "spikes_per_sim_second": round(float(counts.sum() / elapsed)),
            "mean_mv": round(float(self.v.mean()), 3), "compute_ms": round(step_ms, 1),
            "neural_seconds": round(self.total_steps * self.dt_ms / 1000, 3),
            "active_sample": counts[self.display].clip(0, 255).tolist(),
            "vision": np.round(np.column_stack((self.uv["on"], luminance_on)), 3).tolist(),
            "odor_strength": round(odor, 3),
            "integration_mode": "12 ms observation windows; reset to rest each window",
        }

    def geometry(self):
        coords = self.xyz[self.display][:, [0, 2]].copy()
        if len(coords):
            lo, hi = np.percentile(coords, [1, 99], axis=0)
            coords = np.clip((coords - lo) / np.maximum(hi - lo, 1), 0, 1)
        return {"points": np.round(coords, 4).tolist(), "sample_size": len(coords),
                "neurons": self.n, "edges": len(self.data), "motor_populations": {k: len(v) for k, v in self.motor.items()},
                "retina_cells": len(self.on) + len(self.off), "graph_sha256": self.manifest["graph_sha256"]}

    def save(self, path: Path, world):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".partial").open("wb") as f:
            np.savez_compressed(f, v=self.v, refr=self.refr, steps=self.total_steps,
                                rng=json.dumps(self.rng.bit_generator.state), world=json.dumps(world.state()),
                                graph=self.manifest["graph_sha256"])
        path.with_suffix(".partial").replace(path)

    def restore(self, path: Path, world):
        if not path.exists():
            return False
        with np.load(path, allow_pickle=False) as z:
            if str(z["graph"]) != self.manifest["graph_sha256"]:
                raise ValueError("Checkpoint belongs to a different graph")
            if z["v"].shape != self.v.shape or not np.isfinite(z["v"]).all():
                raise ValueError("Invalid checkpoint voltages")
            self.v[:] = z["v"]
            self.refr[:] = z["refr"]
            self.total_steps = int(z["steps"])
            self.rng.bit_generator.state = json.loads(str(z["rng"]))
            world.restore(json.loads(str(z["world"])))
        return True
