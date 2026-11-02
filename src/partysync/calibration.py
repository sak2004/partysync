"""FFT-based calibration helpers and simulated calibration result."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from partysync.core.chirp import find_chirps, make_chirp


@dataclass
class CalibrationResult:
    """Speaker latency-difference calibration result in milliseconds."""

    ok: bool
    reason: str | None
    delta_ms: float | None
    delay_a_ms: float | None
    delay_b_ms: float | None
    min_pmr: float | None


def calibrate_recording(rec: np.ndarray, fs: int, expected_gap_s: float = 1.0) -> CalibrationResult:
    """Estimate B-minus-A latency in milliseconds from two recorded chirps."""
    ref = make_chirp(fs)
    detections = find_chirps(rec, fs, ref, 2, min_sep_s=0.5)
    if len(detections) != 2:
        return CalibrationResult(False, "Both speakers were not heard.", None, None, None, None)
    delta = (detections[1].t_s - detections[0].t_s - expected_gap_s) * 1000
    a, b = (delta, 0.0) if delta > 0 else (0.0, -delta)
    return CalibrationResult(True, None, delta, a, b, min(item.pmr for item in detections))
