"""Channel-mode mixing, stereo conversion, and hard clipping."""

from __future__ import annotations

from enum import Enum

import numpy as np


class ChannelMode(Enum):
    """Which part of the stereo source this speaker plays."""

    STEREO = "stereo"  # L and R as-is
    MONO = "mono"  # (L+R)/2 on every output channel
    LEFT = "left"  # L on every output channel
    RIGHT = "right"  # R on every output channel


def apply_channel_mode(frames: np.ndarray, mode: ChannelMode) -> np.ndarray:
    """Apply a channel mode to stereo frames, returning (n, 2) float32."""
    if frames.ndim == 1:
        frames = frames[:, np.newaxis]
    if frames.shape[1] < 2:
        # Mono input: duplicate to stereo first
        frames = np.column_stack([frames[:, 0], frames[:, 0]])
    if mode == ChannelMode.STEREO:
        return frames[:, :2].copy()
    elif mode == ChannelMode.MONO:
        m = (frames[:, 0] + frames[:, 1]) * 0.5
        return np.column_stack([m, m])
    elif mode == ChannelMode.LEFT:
        return np.column_stack([frames[:, 0], frames[:, 0]])
    elif mode == ChannelMode.RIGHT:
        return np.column_stack([frames[:, 1], frames[:, 1]])
    else:
        return frames[:, :2].copy()


def to_stereo(frames: np.ndarray) -> np.ndarray:
    """Convert any channel layout to stereo (n, 2) float32."""
    if frames.ndim == 1:
        return np.column_stack([frames, frames]).astype(np.float32)
    n_ch = frames.shape[1]
    if n_ch == 1:
        return np.column_stack([frames[:, 0], frames[:, 0]]).astype(np.float32)
    if n_ch == 2:
        return frames.astype(np.float32)
    # More than 2 channels: take the first two
    return frames[:, :2].astype(np.float32)


def to_mono(frames: np.ndarray) -> np.ndarray:
    """Convert stereo (n, 2) to mono (n, 1) by averaging channels."""
    if frames.ndim == 1:
        return frames[:, np.newaxis].astype(np.float32)
    if frames.shape[1] == 1:
        return frames.astype(np.float32)
    return ((frames[:, 0] + frames[:, 1]) * 0.5)[:, np.newaxis].astype(np.float32)


def hard_clip(frames: np.ndarray) -> np.ndarray:
    """Clip sample values to the range [-1, 1] in-place and return the array."""
    return np.clip(frames, -1.0, 1.0, out=frames)
