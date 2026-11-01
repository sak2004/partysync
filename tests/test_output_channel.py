from __future__ import annotations

import numpy as np

from partysync.core.output_channel import OutputChannel


def test_channel_primes_to_safety_target_and_returns_audio() -> None:
    channel = OutputChannel(1_000, block_hint_frames=10, safety_ms=60, ring_seconds=2)
    channel.write(np.ones((60, 2), dtype=np.float32))
    assert channel.stats().primed
    assert channel.stats().target_ms == 60
    assert np.allclose(channel.read(10), 1)


def test_channel_delay_change_causes_a_jump_for_large_error() -> None:
    channel = OutputChannel(1_000, block_hint_frames=10, safety_ms=60, ring_seconds=2)
    channel.set_delay_ms(100)
    channel.write(np.ones((200, 2), dtype=np.float32))
    channel.read(10)
    channel.set_delay_ms(0)
    channel.read(10)
    assert channel.stats().jumps == 1
    assert channel.stats().delay_ms == 0


def test_idle_drain_does_not_count_underrun_and_reprime_is_required() -> None:
    channel = OutputChannel(1_000, block_hint_frames=10, safety_ms=10, ring_seconds=1)
    channel.write(np.ones((10, 2), dtype=np.float32))
    channel.set_source_idle(True)
    channel.read(20)
    assert channel.stats().underruns == 0
    assert not channel.stats().primed


def test_gain_ramp_mute_and_hard_limits() -> None:
    channel = OutputChannel(1_000, block_hint_frames=10, safety_ms=10, ring_seconds=1)
    channel.write(np.ones((20, 2), dtype=np.float32))
    channel.set_gain(2)
    output = channel.read(10).copy()
    assert output[-1, 0] == 1.5
    channel.set_muted(True)
    channel.write(np.ones((10, 2), dtype=np.float32))
    assert channel.read(10)[-1, 0] == 0


def test_ring_overrun_drops_oldest_frames() -> None:
    channel = OutputChannel(100, block_hint_frames=10, safety_ms=10, ring_seconds=1)
    channel.write(np.ones((150, 2), dtype=np.float32))
    assert channel.stats().overruns == 1
    assert channel.stats().primed
