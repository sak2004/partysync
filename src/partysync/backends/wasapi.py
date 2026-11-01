"""Windows WASAPI backend via PyAudioWPatch."""  # pragma: no cover

from __future__ import annotations

import sys
from contextlib import suppress
from typing import Any

import numpy as np

from partysync.backends.base import BackendUnavailable, DeviceInfo, FrameCallback, RenderCallback

if sys.platform == "win32":  # pragma: no cover
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        pyaudio = None
else:
    pyaudio = None


class _WasapiStream:  # pragma: no cover
    """PortAudio stream wrapper; stop and close tolerate Bluetooth errors."""

    def __init__(self, stream: Any, sample_rate: int, channels: int) -> None:
        self._stream, self.sample_rate, self.channels = stream, sample_rate, channels

    def start(self) -> None:
        """Start the PortAudio callback stream."""
        self._stream.start_stream()

    def stop(self) -> None:
        """Stop the stream, ignoring device-removal errors."""
        with suppress(OSError):
            self._stream.stop_stream()

    def close(self) -> None:
        """Close the stream, ignoring device-removal errors."""
        with suppress(OSError):
            self._stream.close()


class WasapiBackend:  # pragma: no cover
    """Windows-only PyAudioWPatch WASAPI callback backend."""

    def __init__(self) -> None:
        if pyaudio is None:
            raise BackendUnavailable("PyAudioWPatch WASAPI is only available on Windows")
        self._pa = pyaudio.PyAudio()
        self.callback_errors = 0

    def _wasapi_devices(self) -> list[dict[str, Any]]:
        info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        host_index = int(info["index"])
        return [
            self._pa.get_device_info_by_host_api_device_index(host_index, local_index)
            for local_index in range(int(info["deviceCount"]))
        ]

    @staticmethod
    def _warning(name: str) -> str | None:
        if "hands-free" in name.lower() or "headset" in name.lower():
            return "Hands-Free profile: low quality, use the Stereo entry"
        return None

    def _info(self, raw: dict[str, Any], kind: str, loopback: bool = False) -> DeviceInfo:
        name = raw["name"].replace(" [Loopback]", "") if loopback else raw["name"]
        channels = int(raw["maxInputChannels"] if kind != "output" else raw["maxOutputChannels"])
        return DeviceInfo(int(raw["index"]), name, kind, channels, int(raw["defaultSampleRate"]), loopback, self._warning(name))

    def list_sources(self) -> list[DeviceInfo]:
        """Return WASAPI capture and loopback source endpoints."""
        loopbacks = [self._info(item, "source", True) for item in self._pa.get_loopback_device_info_generator()]
        inputs = [
            self._info(raw, "source")
            for raw in self._wasapi_devices()
            if raw["maxInputChannels"] > 0
        ]
        return loopbacks + inputs

    def list_outputs(self) -> list[DeviceInfo]:
        """Return WASAPI render endpoints, with hands-free profiles sorted last."""
        result = [
            self._info(raw, "output")
            for raw in self._wasapi_devices()
            if raw["maxOutputChannels"] > 0
        ]
        return sorted(result, key=lambda item: (item.warning is not None, item.name.lower()))

    def list_mics(self) -> list[DeviceInfo]:
        """Return non-loopback WASAPI microphone endpoints."""
        loopback_indices = {item.index for item in self.list_sources() if item.is_loopback}
        return [
            self._info(raw, "mic")
            for raw in self._wasapi_devices()
            if raw["maxInputChannels"] > 0
            and raw["index"] not in loopback_indices
        ]

    def open_source(self, dev: DeviceInfo, on_frames: FrameCallback, block_ms: int) -> _WasapiStream:
        """Open a float32 WASAPI capture stream with exception-contained callbacks."""
        return self._open_input(dev, on_frames, block_ms)

    def open_mic(self, dev: DeviceInfo, on_frames: FrameCallback) -> _WasapiStream:
        """Open a float32 WASAPI microphone callback stream."""
        return self._open_input(dev, on_frames, 10)

    def _open_input(self, dev: DeviceInfo, callback: FrameCallback, block_ms: int) -> _WasapiStream:
        channels, rate = min(2, dev.channels), dev.default_rate

        def capture(data: bytes, frames: int, _: Any, __: Any) -> tuple[None, int]:
            try:
                samples = np.frombuffer(data, dtype=np.float32).reshape(frames, channels)
                callback(samples.copy())
            except Exception:
                self.callback_errors += 1
            return None, pyaudio.paContinue

        stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=dev.index,
            frames_per_buffer=max(1, rate * block_ms // 1000),
            stream_callback=capture,
        )
        return _WasapiStream(stream, rate, channels)

    def open_output(self, dev: DeviceInfo, render: RenderCallback, block_ms: int) -> _WasapiStream:
        """Open a float32 WASAPI render stream with silence on callback failures."""
        channels, rate = min(2, dev.channels), dev.default_rate

        def playback(_: bytes, frames: int, __: Any, ___: Any) -> tuple[bytes, int]:
            try:
                data = np.asarray(render(frames), dtype=np.float32).reshape(frames, channels)
                return data.tobytes(), pyaudio.paContinue
            except Exception:
                self.callback_errors += 1
                return np.zeros((frames, channels), dtype=np.float32).tobytes(), pyaudio.paContinue

        stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=rate,
            output=True,
            output_device_index=dev.index,
            frames_per_buffer=max(1, rate * block_ms // 1000),
            stream_callback=playback,
        )
        return _WasapiStream(stream, rate, channels)
