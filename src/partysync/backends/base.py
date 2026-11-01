"""Backend protocols and device descriptions shared by real and simulated audio I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

FrameCallback = Callable[[np.ndarray], None]
RenderCallback = Callable[[int], np.ndarray]


class BackendUnavailable(RuntimeError):
    """Raised when a platform-specific audio backend cannot be used."""


@dataclass(frozen=True)
class DeviceInfo:
    """Audio endpoint properties; rates are in Hz and index is backend-specific."""

    index: int
    name: str
    kind: Literal["source", "output", "mic"]
    channels: int
    default_rate: int
    is_loopback: bool = False
    warning: str | None = None


class AudioStream(Protocol):
    """A callback stream with sample rate in Hz and number of device channels."""

    sample_rate: int
    channels: int

    def start(self) -> None:
        """Start callback delivery."""

    def stop(self) -> None:
        """Stop callback delivery."""

    def close(self) -> None:
        """Release stream resources."""


class AudioBackend(Protocol):
    """Device enumeration and callback-stream factory interface."""

    def list_sources(self) -> list[DeviceInfo]:
        """Return capture and loopback source endpoints."""

    def list_outputs(self) -> list[DeviceInfo]:
        """Return render endpoints."""

    def list_mics(self) -> list[DeviceInfo]:
        """Return microphone endpoints."""

    def open_source(self, dev: DeviceInfo, on_frames: FrameCallback, block_ms: int) -> AudioStream:
        """Open a source stream with callback frames."""

    def open_output(self, dev: DeviceInfo, render: RenderCallback, block_ms: int) -> AudioStream:
        """Open an output stream with a render callback."""

    def open_mic(self, dev: DeviceInfo, on_frames: FrameCallback) -> AudioStream:
        """Open a microphone stream with callback frames."""
