"""StreamResampler: streaming sample-rate converter wrapping soxr.

Falls back to numpy linear interpolation if soxr is not installed,
which allows tests and CI to run on platforms without a soxr binary wheel.
"""

from __future__ import annotations

import numpy as np

try:
    import soxr

    _HAS_SOXR = True
except ImportError:
    _HAS_SOXR = False


class StreamResampler:
    """Streaming resampler from *in_rate* to *out_rate*.

    If soxr is available, uses soxr.ResampleStream for high-quality resampling.
    Otherwise uses a numpy-based linear interpolation fallback (adequate for tests).
    """

    def __init__(self, in_rate: int, out_rate: int, channels: int = 2) -> None:
        self._in_rate = in_rate
        self._out_rate = out_rate
        self._channels = channels
        self._ratio = out_rate / in_rate

        if _HAS_SOXR and in_rate != out_rate:
            self._resampler = soxr.ResampleStream(
                in_rate, out_rate, channels, dtype="float32"
            )
            self._use_soxr = True
        else:
            self._resampler = None
            self._use_soxr = _HAS_SOXR and in_rate == out_rate
            # Fractional sample accumulator for numpy fallback
            self._frac_accum: float = 0.0

    @property
    def in_rate(self) -> int:
        """Input sample rate in Hz."""
        return self._in_rate

    @property
    def out_rate(self) -> int:
        """Output sample rate in Hz."""
        return self._out_rate

    def process(self, frames: np.ndarray) -> np.ndarray:
        """Resample a block of frames. Input/output shape (n, channels) float32."""
        if self._in_rate == self._out_rate:
            return frames.copy()

        if self._use_soxr and self._resampler is not None:
            return self._resampler.resample_chunk(frames)

        # Numpy linear interpolation fallback
        n_in = frames.shape[0]
        if n_in == 0:
            return np.zeros((0, self._channels), dtype=np.float32)

        # Calculate exact number of output samples
        exact_out = n_in * self._ratio + self._frac_accum
        n_out = int(exact_out)
        self._frac_accum = exact_out - n_out

        if n_out == 0:
            return np.zeros((0, self._channels), dtype=np.float32)

        x_in = np.arange(n_in, dtype=np.float64)
        x_out = np.linspace(0, n_in - 1, n_out, dtype=np.float64)

        out = np.zeros((n_out, self._channels), dtype=np.float32)
        for ch in range(self._channels):
            out[:, ch] = np.interp(x_out, x_in, frames[:, ch]).astype(np.float32)

        return out

    def reset(self) -> None:
        """Reset the resampler state."""
        if self._use_soxr and self._resampler is not None:
            # Re-create the resampler
            self._resampler = soxr.ResampleStream(
                self._in_rate, self._out_rate, self._channels, dtype="float32"
            )
        self._frac_accum = 0.0
