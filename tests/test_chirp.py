from __future__ import annotations

import numpy as np

from partysync.core.chirp import find_chirps, make_chirp, matched_filter_envelope


def test_chirp_peak_and_fades_are_safe() -> None:
    chirp = make_chirp(48_000)
    assert chirp.dtype == np.float32
    assert len(chirp) == 19_200
    assert np.max(np.abs(chirp)) <= 0.5
    assert chirp[0] == 0
    assert chirp[-1] == 0


def test_matched_filter_peak_is_at_signal_start() -> None:
    reference = make_chirp(16_000, dur_s=0.05)
    start = 1_234
    recording = np.zeros(4_000, dtype=np.float32)
    recording[start : start + len(reference)] = reference
    envelope = matched_filter_envelope(recording, reference)
    assert int(np.argmax(envelope)) == start


def test_find_chirps_finds_separated_noisy_chirps() -> None:
    fs = 16_000
    reference = make_chirp(fs, dur_s=0.08)
    recording = np.random.default_rng(4).normal(0, 0.002, 35_000).astype(np.float32)
    starts = [2_000, 14_000, 26_000]
    for start in starts:
        recording[start : start + len(reference)] += reference
    found = find_chirps(recording, fs, reference, 3)
    assert [round(item.t_s * fs) for item in found] == starts
    assert all(item.pmr > 8 for item in found)
