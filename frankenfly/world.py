"""A virtual body and sensory environment; no autonomous navigation rules."""
from __future__ import annotations

import math
import numpy as np


class World:
    width, height = 960, 600
    radius = 24

    def __init__(self):
        self.x, self.y, self.heading = 480., 340., -.2
        self.time = 0.
        self.distance = 0.
        self.contacts = 0
        self.touching = False
        self.stimuli = [{"kind": "light", "x": 680., "y": 210., "power": 1., "until": 120.}]
        self.obstacles = [{"x": 235, "y": 235, "w": 38, "h": 140}, {"x": 680, "y": 360, "w": 130, "h": 28}]
        self.trace = []

    def place(self, kind, x, y, power=1.):
        self.stimuli = [s for s in self.stimuli if s["kind"] != kind]
        self.stimuli.append({"kind": kind, "x": float(x), "y": float(y), "power": float(power), "until": self.time + 45})

    def sense(self, uv):
        """An egocentric ground-plane camera, an explicit modeling choice.

        Ground luminance is sampled at the measured retina columns. This is
        not an anatomically faithful optical reconstruction of a fly's eyes.
        """
        lateral = (uv[:, 0] - .5) * 360
        forward = (.75 - uv[:, 1]) * 300
        x = self.x + np.cos(self.heading) * forward - np.sin(self.heading) * lateral
        y = self.y + np.sin(self.heading) * forward + np.cos(self.heading) * lateral
        light = np.full(len(uv), .07)
        # Fixed physical arena surfaces. Grid and mascot artwork are not input.
        wall = (x < 24) | (x > self.width - 24) | (y < 24) | (y > self.height - 24)
        light[wall] = .48
        for o in self.obstacles:
            inside = (x >= o["x"]) & (x <= o["x"] + o["w"]) & (y >= o["y"]) & (y <= o["y"] + o["h"])
            light[inside] = .36
        for s in self.stimuli:
            d2 = (x - s["x"]) ** 2 + (y - s["y"]) ** 2
            if s["kind"] == "light":
                light += .9 * s["power"] * np.exp(-d2 / (2 * 65 ** 2))
            elif s["kind"] == "shadow":
                # A pulsating dark disk, not a validated looming-threat model.
                radius = 50 + 38 * (.5 + .5 * np.sin(self.time * 2))
                light[d2 < radius ** 2] *= .1
        return np.clip(light, 0, 1)

    def odor_strength(self):
        return min(1., sum(s["power"] * math.exp(-math.hypot(self.x - s["x"], self.y - s["y"]) / 180)
                           for s in self.stimuli if s["kind"] == "odor"))

    def move(self, turn, drive, dt=.1):
        self.time += dt
        self.heading = (self.heading + turn * 2.6 * dt + math.pi) % (2 * math.pi) - math.pi
        nx = self.x + math.cos(self.heading) * drive * 240 * dt
        ny = self.y + math.sin(self.heading) * drive * 240 * dt
        nx = max(self.radius, min(self.width - self.radius, nx))
        ny = max(self.radius, min(self.height - self.radius, ny))
        collided = False
        for o in self.obstacles:
            cx = max(o["x"], min(o["x"] + o["w"], nx))
            cy = max(o["y"], min(o["y"] + o["h"], ny))
            if math.hypot(nx - cx, ny - cy) < self.radius:
                nx, ny, collided = self.x, self.y, True
                break
        collided |= nx in (self.radius, self.width - self.radius) or ny in (self.radius, self.height - self.radius)
        if collided and not self.touching:
            self.contacts += 1
        self.touching = collided
        self.distance += math.hypot(nx - self.x, ny - self.y)
        self.x, self.y = nx, ny
        self.stimuli = [s for s in self.stimuli if s["until"] > self.time]
        self.trace.append([round(self.x, 2), round(self.y, 2)])
        self.trace = self.trace[-450:]

    def state(self):
        return {"x": round(self.x, 3), "y": round(self.y, 3), "heading": self.heading,
                "time": round(self.time, 3), "distance": round(self.distance, 2), "contacts": self.contacts,
                "stimuli": self.stimuli, "obstacles": self.obstacles, "trace": self.trace}

    def restore(self, state):
        for name in ("x", "y", "heading", "time", "distance", "contacts", "stimuli", "trace"):
            if name in state:
                setattr(self, name, state[name])
