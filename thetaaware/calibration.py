"""Measured per-pair, per-angle gate model of IBM's fractional RZZ(theta).

Model of one physical gate on pair (a, b), measured in E2/E4/E6/E7/E8:

    G(theta) = RZZ(theta + delta(theta)) . RZ_a(alpha(theta)) . RZ_b(beta(theta))   (coherent part)
             followed by a depolarising error of size eps(theta)                     (incoherent part)

All functions of theta are linear interpolations over the measured grid and are
clipped (held constant) outside it. `alpha` belongs to pair[0] and `beta` to pair[1].
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def pair_key(a: int, b: int) -> tuple[int, int]:
    return (int(a), int(b))


def parse_pair(s: str) -> tuple[int, int]:
    a, b = s.strip("()[] ").split(",")
    return int(a), int(b)


@dataclass
class PairCal:
    pair: tuple[int, int]
    th: np.ndarray            # grid of the coherent parameters (rad, increasing, within (0, pi/2])
    delta: np.ndarray         # over-rotation: the gate applies theta + delta
    alpha: np.ndarray         # local Z phase on pair[0]
    beta: np.ndarray          # local Z phase on pair[1]
    eps_th: np.ndarray        # grid of eps
    eps: np.ndarray           # incoherent error per gate (mirror-circuit fit)
    reported: float           # IBM-reported two-qubit gate error (same number for RZZ and CZ)
    source: str               # which jobs the numbers come from

    def _i(self, x, grid, vals):
        return float(np.interp(x, grid, vals))

    def at(self, theta: float) -> dict:
        """Model parameters at 0 < theta <= pi/2."""
        return dict(delta=self._i(theta, self.th, self.delta), alpha=self._i(theta, self.th, self.alpha),
                    beta=self._i(theta, self.th, self.beta), eps=max(self._i(theta, self.eps_th, self.eps), 0.0))

    def in_grid(self, theta: float) -> bool:
        return bool(self.th[0] - 1e-9 <= theta <= self.th[-1] + 1e-9)

    def pre_distort(self, theta: float) -> float | None:
        """The angle x to request so that the hardware applies x + delta(x) = theta.
        None when the measured response is not monotonic or theta is outside its range."""
        eff = self.th + self.delta
        if not np.all(np.diff(eff) > 0) or not (eff[0] <= theta <= eff[-1]):
            return None
        return float(np.interp(theta, eff, self.th))

    def oriented(self, a: int, b: int) -> "PairCal":
        """The same calibration seen with qubit a first (alpha and beta swap if needed)."""
        if (a, b) == self.pair:
            return self
        if (b, a) != self.pair:
            raise KeyError((a, b))
        return PairCal((a, b), self.th, self.delta, self.beta, self.alpha, self.eps_th, self.eps, self.reported, self.source)


class Calibration(dict):
    """{(a, b): PairCal}; lookups work in either qubit order."""

    def get_pair(self, a: int, b: int) -> PairCal | None:
        if (a, b) in self:
            return self[(a, b)]
        if (b, a) in self:
            return self[(b, a)].oriented(a, b)
        return None

    def to_json(self) -> dict:
        return {str(k): dict(th=v.th.tolist(), delta=v.delta.tolist(), alpha=v.alpha.tolist(), beta=v.beta.tolist(),
                             eps_th=v.eps_th.tolist(), eps=v.eps.tolist(), reported=v.reported, source=v.source)
                for k, v in self.items()}

    @classmethod
    def from_json(cls, d: dict) -> "Calibration":
        out = cls()
        for k, v in d.items():
            p = parse_pair(k)
            out[p] = PairCal(p, np.array(v["th"]), np.array(v["delta"]), np.array(v["alpha"]), np.array(v["beta"]),
                             np.array(v["eps_th"]), np.array(v["eps"]), float(v["reported"]), v["source"])
        return out


def from_jobs(round_file: str, eps_file: str, reported_file: str) -> Calibration:
    """Build a calibration from a round-2 calibration (alpha, beta, theta + delta), an eps sweep
    (calib_*.json written by 04_analyze_pilot.py) and the IBM-reported errors stored with a sweep job."""
    rnd = json.loads((ROOT / round_file).read_text())
    eps = json.loads((ROOT / eps_file).read_text())["pairs"]
    rep = json.loads((ROOT / reported_file).read_text())["reported_rzz_error"]
    src = f"coherent: {rnd['calib_job']}; eps: {json.loads((ROOT / eps_file).read_text())['source_job']}"
    out = Calibration()
    for k, c in rnd["calibration"].items():
        p = parse_pair(k)
        th = np.array(c["th"], float)
        e = eps[k]
        out[p] = PairCal(p, th, np.array(c["eff"], float) - th, np.array(c["alpha"], float), np.array(c["beta"], float),
                         np.array(e["eps_theta"], float), np.array(e["eps"], float), float(rep[k]), src)
    return out


# The calibrations that existed before each later job (see RESEARCH_LOG.md for the timeline, all 14 Oct 2026).
def marrakesh_after_e4() -> Calibration:
    """E4 coherent calibration (19:10) + E2 eps (18:37). Available before E8, E9 and E10."""
    return from_jobs("round2_db7t6ier6oqs738898ig.json", "calib_db7sns0r1c5c738l7vm0.json", "confirm_db7sns0r1c5c738l7vm0.json")


def marrakesh_after_e8() -> Calibration:
    """E4 coherent calibration + E8 eps (19:23). Available before E9 (20:14) and E10 (20:18)."""
    return from_jobs("round2_db7t6ier6oqs738898ig.json", "calib_marrakesh2.json", "sweepM2_db7td8or1c5c738l94dg.json")


def kingston_e6() -> Calibration:
    """E6 coherent calibration (its own calibration job) + E7 eps (19:23)."""
    return from_jobs("round2k_db7teq6il99s73forh20.json", "calib_kingston.json", "sweepK_db7td8or1c5c738l94d0.json")
