"""Per-output ring buffer, delay control, drift correction, and gain ramps."""

from __future__ import annotations

import numpy as np

from partysync.core.constants import (
    CROSSFADE_MS,
    FILTER_TAU_S,
    GAIN_RAMP_MS,
    JUMP_MS_MIN,
    MAX_DELAY_MS,
    RING_SECONDS,
    SAFETY_MS,
    SLIP_DEADBAND_MS,
)
from partysync.core.stats import ChannelStats


class OutputChannel:
    """SPSC output buffer; timing controls use milliseconds and reads use frames."""

    def __init__(
        self,
        sample_rate: int,
        channels: int = 2,
        *,
        block_hint_frames: int = 480,
        safety_ms: float = SAFETY_MS,
        ring_seconds: float = RING_SECONDS,
    ) -> None:
        if sample_rate <= 0 or channels <= 0 or block_hint_frames <= 0 or ring_seconds <= 0:
            raise ValueError("sample rate, channels, block hint, and ring length must be positive")
        self._rate, self._channels = sample_rate, channels
        self._capacity = max(1, int(ring_seconds * sample_rate))
        self._buf = np.zeros((self._capacity, channels), dtype=np.float32)
        self._write_idx = self._read_idx = 0
        self._safety_ms, self._delay_ms = safety_ms, 0.0
        self._target_frames = self._ms_to_frames(safety_ms)
        self._primed = self._source_idle = False
        self._underruns = self._overruns = self._jumps = self._slips = 0
        self._err_filt = 0.0
        self._force_jump = False
        self._block_hint = block_hint_frames
        self._jump_threshold_frames = self._ms_to_frames(
            max(JUMP_MS_MIN, 3_000.0 * block_hint_frames / sample_rate)
        )
        self._slip_deadband_frames = self._ms_to_frames(SLIP_DEADBAND_MS)
        self._crossfade_frames = max(1, self._ms_to_frames(CROSSFADE_MS))
        self._gain = self._target_gain = 1.0
        self._muted = False
        self._gain_ramp_frames = max(1, self._ms_to_frames(GAIN_RAMP_MS))
        self._scratch_size = 0
        self._out = np.empty((0, channels), dtype=np.float32)
        self._old = np.empty((0, channels), dtype=np.float32)
        self._input = np.empty((0, channels), dtype=np.float32)
        self._ensure_scratch(block_hint_frames)
        slots = max(10, int(20 * sample_rate / block_hint_frames))
        self._drift_times = np.zeros(slots, dtype=np.float64)
        self._drift_fills = np.zeros(slots, dtype=np.float64)
        self._drift_idx = self._drift_count = self._total_read_frames = 0
        self._drift_ppm = self._peak = self._rms = 0.0

    def _ms_to_frames(self, ms: float) -> int:
        return int(ms * self._rate / 1000.0)

    def _ensure_scratch(self, n: int) -> None:
        """Grow callback scratch storage once when a larger block is negotiated."""
        needed = max(n + 1, 1)
        if needed <= self._scratch_size:
            return
        self._scratch_size = needed
        self._out = np.zeros((needed, self._channels), dtype=np.float32)
        self._old = np.zeros_like(self._out)
        self._input = np.zeros_like(self._out)

    def _copy_from(self, pos: int, n: int, dst: np.ndarray) -> None:
        """Copy n frames from monotonic pos into preallocated dst."""
        start = pos % self._capacity
        first = min(n, self._capacity - start)
        dst[:first] = self._buf[start : start + first]
        if first < n:
            dst[first:n] = self._buf[: n - first]

    def write(self, frames: np.ndarray) -> None:
        """Write float32 (frames, channels) from the capture callback."""
        if frames.ndim != 2 or frames.shape[1] != self._channels:
            raise ValueError(f"frames must have shape (n, {self._channels})")
        n = frames.shape[0]
        if n == 0:
            return
        if n >= self._capacity:
            frames, n = frames[-self._capacity :], self._capacity
            self._read_idx = self._write_idx
            self._overruns += 1
        fill = self._write_idx - self._read_idx
        if n > self._capacity - fill:
            self._read_idx += n - (self._capacity - fill)
            self._overruns += 1
        pos = self._write_idx % self._capacity
        first = min(n, self._capacity - pos)
        self._buf[pos : pos + first] = frames[:first]
        if first < n:
            self._buf[: n - first] = frames[first:]
        self._write_idx += n
        if not self._primed and self._write_idx - self._read_idx >= self._target_frames:
            self._read_idx = self._write_idx - self._target_frames
            self._primed, self._err_filt = True, 0.0
            self._force_jump = False

    def write_silence(self, n: int) -> None:
        """Write n silent frames without allocating an audio block."""
        if n < 0:
            raise ValueError("frame count must not be negative")
        while n:
            take = min(n, self._scratch_size)
            self._input[:take].fill(0.0)
            self.write(self._input[:take])
            n -= take

    def read(self, n: int) -> np.ndarray:
        """Read n frames for a render callback as float32 (n, channels)."""
        if n < 0:
            raise ValueError("frame count must not be negative")
        self._ensure_scratch(n)
        out = self._out[:n]
        out.fill(0.0)
        if n == 0 or not self._primed:
            return out
        write_idx = self._write_idx
        fill = write_idx - self._read_idx
        if fill < n:
            if fill > 0:
                self._copy_from(self._read_idx, fill, out)
                self._read_idx += fill
            if not self._source_idle:
                self._underruns += 1
            self._primed = False
            self._apply_gain(out)
            self._update_levels(out)
            return out
        err = fill - self._target_frames
        alpha = min(1.0, (n / self._rate) / FILTER_TAU_S) if FILTER_TAU_S else 1.0
        self._err_filt = (1.0 - alpha) * self._err_filt + alpha * err
        if (self._force_jump and fill >= self._target_frames) or abs(err) > self._jump_threshold_frames:
            self._jump(write_idx, n, out)
        elif abs(self._err_filt) > self._slip_deadband_frames:
            self._slip(n, out)
        else:
            self._copy_from(self._read_idx, n, out)
            self._read_idx += n
        self._update_drift(fill, n)
        self._apply_gain(out)
        self._update_levels(out)
        return out

    def _jump(self, write_idx: int, n: int, out: np.ndarray) -> None:
        self._copy_from(self._read_idx, n, self._old)
        new_pos = write_idx - self._target_frames
        self._copy_from(new_pos, n, out)
        fade = min(self._crossfade_frames, n)
        if fade:
            ramp = np.arange(fade, dtype=np.float32) / max(fade - 1, 1)
            out[:fade] = self._old[:fade] * (1.0 - ramp[:, None]) + out[:fade] * ramp[:, None]
        self._read_idx = new_pos + n
        self._jumps += 1
        self._err_filt = 0.0
        self._force_jump = False

    def _slip(self, n: int, out: np.ndarray) -> None:
        direction = 1 if self._err_filt > 0 else -1
        consume = n + direction
        if consume <= 0 or consume > self._write_idx - self._read_idx:
            self._copy_from(self._read_idx, n, out)
            self._read_idx += n
            return
        source = self._input[:consume]
        self._copy_from(self._read_idx, consume, source)
        self._read_idx += consume
        x = np.linspace(0.0, consume - 1, n, dtype=np.float32)
        for channel in range(self._channels):
            out[:, channel] = np.interp(x, np.arange(consume), source[:, channel])
        self._slips += 1

    def _apply_gain(self, out: np.ndarray) -> None:
        target = 0.0 if self._muted else self._target_gain
        if self._gain == target:
            out *= target
            return
        ramp_frames = min(len(out), self._gain_ramp_frames)
        if ramp_frames:
            ramp = np.linspace(self._gain, target, ramp_frames, dtype=np.float32)
            out[:ramp_frames] *= ramp[:, None]
        if ramp_frames < len(out):
            out[ramp_frames:] *= target
        self._gain = target

    def _update_drift(self, fill: int, n: int) -> None:
        self._total_read_frames += n
        slot = self._drift_idx % len(self._drift_times)
        self._drift_times[slot], self._drift_fills[slot] = self._total_read_frames, fill
        self._drift_idx += 1
        self._drift_count = min(self._drift_count + 1, len(self._drift_times))
        if self._drift_count < 10:
            return
        indices = (np.arange(self._drift_count) + self._drift_idx - self._drift_count) % len(
            self._drift_times
        )
        time, levels = self._drift_times[indices], self._drift_fills[indices]
        centered = time - time.mean()
        denominator = np.dot(centered, centered)
        if denominator:
            self._drift_ppm = float(np.dot(centered, levels - levels.mean()) / denominator * 1e6)

    def _update_levels(self, out: np.ndarray) -> None:
        if len(out):
            self._peak = float(np.max(np.abs(out)))
            self._rms = float(np.sqrt(np.mean(np.square(out, dtype=np.float64))))

    def set_delay_ms(self, ms: float) -> None:
        """Set extra delay in milliseconds, clamped to 0 through MAX_DELAY_MS."""
        previous_target = self._target_frames
        self._delay_ms = max(0.0, min(MAX_DELAY_MS, float(ms)))
        self._target_frames = self._ms_to_frames(self._safety_ms + self._delay_ms)
        self._force_jump = abs(self._target_frames - previous_target) > self._ms_to_frames(JUMP_MS_MIN)
        self._err_filt = float(self._write_idx - self._read_idx - self._target_frames)

    def set_gain(self, gain: float) -> None:
        """Set linear gain (0 through 1.5), ramped by the next render callback."""
        self._target_gain = max(0.0, min(1.5, float(gain)))

    def set_muted(self, muted: bool) -> None:
        """Set mute state, which ramps gain to zero on the next callback."""
        self._muted = bool(muted)

    def set_source_idle(self, idle: bool) -> None:
        """Mark whether capture callbacks are currently idle."""
        self._source_idle = bool(idle)

    def stats(self) -> ChannelStats:
        """Return a point-in-time statistics snapshot in milliseconds and ppm."""
        fill = self._write_idx - self._read_idx
        return ChannelStats(
            fill_ms=fill * 1000.0 / self._rate,
            target_ms=self._target_frames * 1000.0 / self._rate,
            delay_ms=self._delay_ms,
            underruns=self._underruns,
            overruns=self._overruns,
            jumps=self._jumps,
            slips=self._slips,
            drift_ppm_estimate=self._drift_ppm,
            primed=self._primed,
            peak=self._peak,
            rms=self._rms,
        )
