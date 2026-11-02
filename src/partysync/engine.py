"""Audio routing controller used by CLI and web dashboards."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

from partysync.backends.base import AudioBackend, AudioStream, DeviceInfo
from partysync.calibration import CalibrationResult, calibrate_recording
from partysync.core.chirp import make_chirp
from partysync.core.constants import BLOCK_MS, IDLE_SOURCE_MS
from partysync.core.mixing import ChannelMode, apply_channel_mode, hard_clip, to_mono, to_stereo
from partysync.core.output_channel import OutputChannel
from partysync.core.resample import StreamResampler


@dataclass
class EngineStats:
    """Live audio routing state."""

    running: bool
    source_peak: float
    source_rms: float
    source_idle: bool
    a: dict
    b: dict


class Engine:
    """Route one source to two independently delayed output devices."""

    def __init__(self, backend: AudioBackend, *, block_ms: int = BLOCK_MS) -> None:
        self.backend, self.block_ms = backend, block_ms
        self._streams: list[AudioStream] = []
        self._channels: dict[str, OutputChannel] = {}
        self._resamplers: dict[str, StreamResampler] = {}
        self._modes = {"A": ChannelMode.STEREO, "B": ChannelMode.STEREO}
        self._source_rate = 0
        self._last_capture = 0.0
        self._source_peak = self._source_rms = 0.0
        self.running = False
        self._outputs: dict[str, DeviceInfo] = {}

    def start(self, source: DeviceInfo, out_a: DeviceInfo, out_b: DeviceInfo) -> None:
        """Start routing selected endpoints; raises ValueError for feedback configurations."""
        if source.index in {out_a.index, out_b.index} or out_a.index == out_b.index:
            raise ValueError("source and outputs must be three distinct endpoints")
        self.stop()
        self._source_rate = source.default_rate
        self._outputs = {"A": out_a, "B": out_b}
        self._channels = {key: OutputChannel(dev.default_rate, 2) for key, dev in {"A": out_a, "B": out_b}.items()}
        self._resamplers = {
            key: StreamResampler(source.default_rate, dev.default_rate)
            for key, dev in {"A": out_a, "B": out_b}.items()
        }
        self._streams = [
            self.backend.open_source(source, self._on_source, self.block_ms),
            self.backend.open_output(out_a, lambda n: self._render("A", n, out_a.channels), self.block_ms),
            self.backend.open_output(out_b, lambda n: self._render("B", n, out_b.channels), self.block_ms),
        ]
        for stream in self._streams:
            stream.start()
        self.running, self._last_capture = True, time.monotonic()

    def stop(self) -> None:
        """Stop and close all active streams."""
        for stream in self._streams:
            try:
                stream.stop()
                stream.close()
            except OSError:
                pass
        self._streams.clear()
        self.running = False

    def _on_source(self, frames: np.ndarray) -> None:
        try:
            stereo = to_stereo(frames)
            self._source_peak = float(np.max(np.abs(stereo))) if len(stereo) else 0.0
            self._source_rms = float(np.sqrt(np.mean(stereo**2))) if len(stereo) else 0.0
            self._last_capture = time.monotonic()
            for key, channel in self._channels.items():
                channel.set_source_idle(False)
                channel.write(self._resamplers[key].process(apply_channel_mode(stereo, self._modes[key])))
        except Exception:
            return

    def _render(self, key: str, frames: int, channels: int) -> np.ndarray:
        channel = self._channels[key]
        if time.monotonic() - self._last_capture > IDLE_SOURCE_MS / 1000:
            channel.set_source_idle(True)
        output = hard_clip(channel.read(frames))
        return to_mono(output) if channels == 1 else output

    def set_delay_ms(self, channel: Literal["A", "B"], ms: float) -> None:
        """Set a channel delay in milliseconds."""
        self._channels[channel].set_delay_ms(ms)

    def set_gain(self, channel: Literal["A", "B"], gain: float) -> None:
        """Set a channel linear gain."""
        self._channels[channel].set_gain(gain)

    def set_muted(self, channel: Literal["A", "B"], muted: bool) -> None:
        """Set a channel mute state."""
        self._channels[channel].set_muted(muted)

    def set_mode(self, channel: Literal["A", "B"], mode: ChannelMode | str) -> None:
        """Set a channel playback mode."""
        self._modes[channel] = ChannelMode(mode)

    def calibrate_simulated(self) -> CalibrationResult:
        """Run matched-filter calibration against simulated endpoint latency."""
        if not self.running or not hasattr(self.backend, "world"):
            return CalibrationResult(False, "Start simulated routing before calibration.", None, None, None, None)
        world = self.backend.world
        a = world._devices[self._outputs["A"].index]
        b = world._devices[self._outputs["B"].index]
        fs, ref, gap = 48_000, make_chirp(48_000), 1.0
        first = int((0.2 + (a.latency_ms + a.acoustic_delay_ms) / 1000) * fs)
        second = int((0.2 + gap + (b.latency_ms + b.acoustic_delay_ms) / 1000) * fs)
        rec = np.random.default_rng(7).normal(0, 0.001, second + len(ref) + fs).astype(np.float32)
        rec[first : first + len(ref)] += ref
        rec[second : second + len(ref)] += ref
        result = calibrate_recording(rec, fs, gap)
        if result.ok:
            self.set_delay_ms("A", result.delay_a_ms or 0)
            self.set_delay_ms("B", result.delay_b_ms or 0)
        return result

    def stats(self) -> EngineStats:
        """Return live routing statistics."""
        empty: dict = {
            "fill_ms": 0,
            "target_ms": 0,
            "delay_ms": 0,
            "slips": 0,
            "jumps": 0,
            "underruns": 0,
            "peak": 0,
            "rms": 0,
        }
        return EngineStats(
            self.running,
            self._source_peak,
            self._source_rms,
            time.monotonic() - self._last_capture > 0.1,
            asdict(self._channels["A"].stats()) if "A" in self._channels else empty,
            asdict(self._channels["B"].stats()) if "B" in self._channels else empty,
        )
