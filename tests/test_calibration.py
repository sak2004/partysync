from __future__ import annotations

import numpy as np

from partysync.calibration import calibrate_recording
from partysync.cli import fake_backend
from partysync.core.chirp import make_chirp
from partysync.engine import Engine


def test_recorded_chirps_recover_latency_delta() -> None:
    fs = 48_000
    ref = make_chirp(fs)
    rec = np.zeros(150_000, np.float32)
    rec[10_000 : 10_000 + len(ref)] += ref
    rec[64_800 : 64_800 + len(ref)] += ref
    result = calibrate_recording(rec, fs, 1.0)
    assert result.ok and abs(result.delta_ms - 141.6667) < 0.1


def test_simulated_engine_calibration_applies_faster_delay() -> None:
    backend = fake_backend()
    engine = Engine(backend)
    engine.start(backend.list_sources()[0], *backend.list_outputs()[:2])
    backend.world.run(0.2)
    result = engine.calibrate_simulated()
    assert result.ok and result.delay_a_ms and result.delay_a_ms > 130
