"""Chirp synthesis and FFT matched-filter detection for calibration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from partysync.core.constants import CHIRP_AMP, CHIRP_DUR_S, CHIRP_F0, CHIRP_F1, CHIRP_FADE_MS


def make_chirp(
    fs: int,
    dur_s: float = CHIRP_DUR_S,
    f0: float = CHIRP_F0,
    f1: float = CHIRP_F1,
    amp: float = CHIRP_AMP,
    fade_ms: float = CHIRP_FADE_MS,
) -> np.ndarray:
    """Return a mono float32 linear chirp with fades and a safe <= -6 dBFS peak."""
    if fs <= 0 or dur_s <= 0 or f0 <= 0 or f1 <= 0 or fade_ms < 0:
        raise ValueError("invalid chirp parameters")
    n = max(1, int(round(fs * dur_s)))
    time = np.arange(n, dtype=np.float64) / fs
    phase = 2 * np.pi * (f0 * time + (f1 - f0) * time**2 / (2 * dur_s))
    chirp = min(float(amp), CHIRP_AMP) * np.sin(phase)
    fade = min(n // 2, int(round(fs * fade_ms / 1000)))
    if fade:
        window = np.linspace(0.0, 1.0, fade, endpoint=True)
        chirp[:fade] *= window
        chirp[-fade:] *= window[::-1]
    return chirp.astype(np.float32)


def _analytic(signal: np.ndarray) -> np.ndarray:
    """Return the analytic signal using a full complex FFT."""
    spectrum = np.fft.fft(signal)
    weights = np.zeros(len(signal))
    weights[0] = 1
    if len(signal) % 2 == 0:
        weights[len(signal) // 2] = 1
        weights[1 : len(signal) // 2] = 2
    else:
        weights[1 : (len(signal) + 1) // 2] = 2
    return np.fft.ifft(spectrum * weights)


def matched_filter_envelope(rec: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Return matched-filter magnitude indexed by each possible reference start sample."""
    recording = np.asarray(rec, dtype=np.float64).reshape(-1)
    reference = np.asarray(ref, dtype=np.float64).reshape(-1)
    if len(recording) < len(reference) or not len(reference):
        return np.empty(0, dtype=np.float64)
    matched = np.conjugate(_analytic(reference[::-1]))
    full_length = len(recording) + len(reference) - 1
    fft_length = 1 << (full_length - 1).bit_length()
    correlation = np.fft.ifft(np.fft.fft(recording, fft_length) * np.fft.fft(matched, fft_length))
    start = len(reference) - 1
    return np.abs(correlation[start : start + len(recording) - len(reference) + 1])


@dataclass
class Detection:
    """A chirp start time in seconds and its peak-to-median ratio."""

    t_s: float
    pmr: float


def find_chirps(
    rec: np.ndarray, fs: int, ref: np.ndarray, n_expected: int, min_sep_s: float = 0.5
) -> list[Detection]:
    """Greedily find up to n_expected chirps, separated by min_sep_s seconds."""
    if fs <= 0 or n_expected < 0 or min_sep_s < 0:
        raise ValueError("invalid detection parameters")
    envelope = matched_filter_envelope(rec, ref)
    if not len(envelope):
        return []
    median = max(float(np.median(envelope)), np.finfo(np.float64).tiny)
    working = envelope.copy()
    separation = int(round(min_sep_s * fs))
    found: list[Detection] = []
    for _ in range(n_expected):
        index = int(np.argmax(working))
        peak = float(working[index])
        pmr = peak / median
        if pmr < 3:
            break
        offset = 0.0
        if 0 < index < len(working) - 1:
            left, centre, right = working[index - 1 : index + 2]
            denominator = left - 2 * centre + right
            if denominator:
                offset = float(np.clip(0.5 * (left - right) / denominator, -1.0, 1.0))
        found.append(Detection((index + offset) / fs, pmr))
        working[max(0, index - separation) : index + separation + 1] = 0
    return sorted(found, key=lambda item: item.t_s)
