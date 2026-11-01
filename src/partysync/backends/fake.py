"""Deterministic virtual audio devices for hardware-independent tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from partysync.backends.base import DeviceInfo, FrameCallback, RenderCallback

SignalKind = Literal["sine", "noise", "click", "silence"]


@dataclass
class FakeSource:
    """Configurable source signal; timing fields use Hz, ppm, and frames."""

    device: DeviceInfo
    block_frames: int
    signal: SignalKind = "sine"
    frequency_hz: float = 440.0
    amplitude: float = 0.25
    clock_ppm: float = 0.0
    jitter_ms: float = 0.0
    no_callbacks_while_silent: bool = False


@dataclass
class FakeOutput:
    """Configurable render endpoint; latency and acoustic delay are milliseconds."""

    device: DeviceInfo
    block_frames: int
    latency_ms: float = 100.0
    acoustic_delay_ms: float = 0.0
    clock_ppm: float = 0.0
    disconnected: bool = False


@dataclass
class FakeMic:
    """Configurable mic hearing summed fake outputs, with optional noise and echoes."""

    device: DeviceInfo
    block_frames: int
    clock_ppm: float = 0.0
    noise_std: float = 0.0
    reverb: tuple[tuple[float, float], ...] = ()
    muted: bool = False


class FakeStream:
    """Virtual callback stream driven only by FakeWorld.run(seconds)."""

    def __init__(
        self, world: FakeWorld, kind: str, device: DeviceInfo, callback: FrameCallback | RenderCallback
    ) -> None:
        self._world, self._kind, self.device, self._callback = world, kind, device, callback
        self.sample_rate, self.channels = device.default_rate, device.channels
        self.active = False
        self.closed = False

    def start(self) -> None:
        """Start callback delivery."""
        if not self.closed:
            self.active = True

    def stop(self) -> None:
        """Stop callback delivery."""
        self.active = False

    def close(self) -> None:
        """Release stream resources."""
        self.active, self.closed = False, True


class FakeWorld:
    """Deterministic virtual clock and endpoint collection; run accepts seconds."""

    def __init__(self, seed: int = 0) -> None:
        self.time_s = 0.0
        self._rng = np.random.default_rng(seed)
        self._devices: dict[int, FakeSource | FakeOutput | FakeMic] = {}
        self._streams: list[FakeStream] = []
        self._next_index = 0
        self._next_due: dict[int, float] = {}
        self._sample_cursor: dict[int, int] = {}
        self._air: list[tuple[float, np.ndarray]] = []

    def add_source(
        self, name: str = "Fake loopback", *, rate: int = 48_000, channels: int = 2, **kwargs: object
    ) -> DeviceInfo:
        """Add a programmable source endpoint and return its DeviceInfo."""
        return self._add("source", name, rate, channels, True, FakeSource, kwargs)

    def add_output(
        self, name: str = "Fake output", *, rate: int = 48_000, channels: int = 2, **kwargs: object
    ) -> DeviceInfo:
        """Add a render endpoint and return its DeviceInfo."""
        return self._add("output", name, rate, channels, False, FakeOutput, kwargs)

    def add_mic(
        self, name: str = "Fake microphone", *, rate: int = 48_000, channels: int = 1, **kwargs: object
    ) -> DeviceInfo:
        """Add a microphone endpoint and return its DeviceInfo."""
        return self._add("mic", name, rate, channels, False, FakeMic, kwargs)

    def _add(
        self,
        kind: Literal["source", "output", "mic"],
        name: str,
        rate: int,
        channels: int,
        loopback: bool,
        config_type: type[FakeSource] | type[FakeOutput] | type[FakeMic],
        kwargs: object,
    ) -> DeviceInfo:
        device = DeviceInfo(self._next_index, name, kind, channels, rate, loopback)
        self._next_index += 1
        self._devices[device.index] = config_type(device=device, block_frames=rate // 100, **kwargs)
        return device

    def _stream(self, kind: str, device: DeviceInfo, callback: FrameCallback | RenderCallback) -> FakeStream:
        if device.index not in self._devices:
            raise ValueError(f"unknown fake device {device.index}")
        stream = FakeStream(self, kind, device, callback)
        self._streams.append(stream)
        self._next_due[id(stream)] = self.time_s
        self._sample_cursor[id(stream)] = 0
        return stream

    def run(self, seconds: float) -> None:
        """Advance virtual time by seconds, firing callbacks in deterministic time order."""
        if seconds < 0:
            raise ValueError("seconds must not be negative")
        end = self.time_s + seconds
        while True:
            active = [stream for stream in self._streams if stream.active and not stream.closed]
            if not active:
                break
            stream = min(active, key=lambda item: self._next_due[id(item)])
            due = self._next_due[id(stream)]
            if due >= end:
                break
            self.time_s = due
            self._fire(stream)
            self._next_due[id(stream)] = due + self._period(stream)
        self.time_s = end

    def _period(self, stream: FakeStream) -> float:
        config = self._devices[stream.device.index]
        rate = stream.sample_rate * (1 + config.clock_ppm * 1e-6)
        period = config.block_frames / rate
        if isinstance(config, FakeSource) and config.jitter_ms:
            period += self._rng.uniform(-config.jitter_ms, config.jitter_ms) / 1000
        return max(period, 1e-6)

    def _fire(self, stream: FakeStream) -> None:
        config = self._devices[stream.device.index]
        if stream._kind == "source":
            assert isinstance(config, FakeSource)
            frames = self._source_frames(stream, config)
            if not (config.no_callbacks_while_silent and config.signal == "silence"):
                stream._callback(frames)
        elif stream._kind == "output":
            assert isinstance(config, FakeOutput)
            if config.disconnected:
                return
            frames = np.asarray(stream._callback(config.block_frames), dtype=np.float32)
            if frames.shape != (config.block_frames, config.device.channels):
                raise ValueError("fake output callback returned an unexpected frame shape")
            arrival = self.time_s + (config.latency_ms + config.acoustic_delay_ms) / 1000
            self._air.append((arrival, frames.copy()))
        else:
            assert isinstance(config, FakeMic)
            stream._callback(self._mic_frames(config))

    def _source_frames(self, stream: FakeStream, config: FakeSource) -> np.ndarray:
        start = self._sample_cursor[id(stream)]
        self._sample_cursor[id(stream)] += config.block_frames
        time = (start + np.arange(config.block_frames)) / config.device.default_rate
        if config.signal == "sine":
            mono = config.amplitude * np.sin(2 * np.pi * config.frequency_hz * time)
        elif config.signal == "noise":
            mono = self._rng.normal(0, config.amplitude, config.block_frames)
        elif config.signal == "click":
            mono = np.zeros(config.block_frames)
            mono[(start + np.arange(config.block_frames)) % config.device.default_rate == 0] = config.amplitude
        else:
            mono = np.zeros(config.block_frames)
        return np.broadcast_to(mono[:, None], (config.block_frames, config.device.channels)).astype(
            np.float32
        )

    def _mic_frames(self, config: FakeMic) -> np.ndarray:
        frames = np.zeros((config.block_frames, config.device.channels), dtype=np.float32)
        if config.muted:
            return frames
        start, end = self.time_s, self.time_s + config.block_frames / config.device.default_rate
        heard = [(arrival, block) for arrival, block in self._air if start <= arrival < end]
        self._air = [(arrival, block) for arrival, block in self._air if arrival >= start]
        for arrival, block in heard:
            offset = int((arrival - start) * config.device.default_rate)
            count = min(len(block), config.block_frames - offset)
            if count > 0:
                mono = block[:count].mean(axis=1)
                frames[offset : offset + count] += mono[:, None]
                for delay_ms, gain in config.reverb:
                    echo = offset + int(delay_ms * config.device.default_rate / 1000)
                    echo_count = min(count, config.block_frames - echo)
                    if echo_count > 0:
                        frames[echo : echo + echo_count] += mono[:echo_count, None] * gain
        if config.noise_std:
            frames += self._rng.normal(0, config.noise_std, frames.shape).astype(np.float32)
        return frames


class FakeBackend:
    """AudioBackend implementation backed by a deterministic FakeWorld."""

    def __init__(self, world: FakeWorld | None = None) -> None:
        self.world = world or FakeWorld()

    def list_sources(self) -> list[DeviceInfo]:
        """Return configured fake source endpoints."""
        return self._list("source")

    def list_outputs(self) -> list[DeviceInfo]:
        """Return configured fake output endpoints."""
        return self._list("output")

    def list_mics(self) -> list[DeviceInfo]:
        """Return configured fake microphone endpoints."""
        return self._list("mic")

    def _list(self, kind: str) -> list[DeviceInfo]:
        return [item.device for item in self.world._devices.values() if item.device.kind == kind]

    def open_source(self, dev: DeviceInfo, on_frames: FrameCallback, block_ms: int) -> FakeStream:
        """Open fake source callback stream; block_ms selects its block size."""
        config = self._require(dev, FakeSource)
        config.block_frames = max(1, round(dev.default_rate * block_ms / 1000))
        return self.world._stream("source", dev, on_frames)

    def open_output(self, dev: DeviceInfo, render: RenderCallback, block_ms: int) -> FakeStream:
        """Open fake output callback stream; block_ms selects its block size."""
        config = self._require(dev, FakeOutput)
        config.block_frames = max(1, round(dev.default_rate * block_ms / 1000))
        return self.world._stream("output", dev, render)

    def open_mic(self, dev: DeviceInfo, on_frames: FrameCallback) -> FakeStream:
        """Open fake microphone callback stream."""
        self._require(dev, FakeMic)
        return self.world._stream("mic", dev, on_frames)

    def disconnect(self, dev: DeviceInfo) -> None:
        """Disconnect an output endpoint in the virtual world."""
        self._require(dev, FakeOutput).disconnected = True

    def _require(self, dev: DeviceInfo, expected: type[FakeSource] | type[FakeOutput] | type[FakeMic]):
        config = self.world._devices.get(dev.index)
        if not isinstance(config, expected):
            raise ValueError(f"{dev.name!r} is not a compatible fake device")
        return config
