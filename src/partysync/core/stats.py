"""Dataclasses for runtime statistics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChannelStats:
    """Per-output-channel statistics snapshot."""

    fill_ms: float  # current ring buffer fill level in milliseconds
    target_ms: float  # current target fill level in milliseconds
    delay_ms: float  # current user-set delay in milliseconds
    underruns: int  # total underrun count
    overruns: int  # total overrun count
    jumps: int  # total jump (gross correction) count
    slips: int  # total slip (fine correction) count
    drift_ppm_estimate: float  # estimated clock drift in ppm
    primed: bool  # True if the channel has enough data to output audio
    peak: float  # recent peak amplitude (linear, 0..1)
    rms: float  # recent RMS amplitude (linear)
