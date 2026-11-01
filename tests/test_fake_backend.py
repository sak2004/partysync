from __future__ import annotations

import numpy as np

from partysync.backends.fake import FakeBackend, FakeWorld


def test_fake_world_delivers_source_and_output_callbacks() -> None:
    world = FakeWorld(seed=1)
    backend = FakeBackend(world)
    source, output = world.add_source(), world.add_output()
    captured: list[np.ndarray] = []
    source_stream = backend.open_source(source, captured.append, 10)
    output_stream = backend.open_output(output, lambda count: np.ones((count, 2), np.float32), 10)
    source_stream.start()
    output_stream.start()
    world.run(0.05)
    assert len(captured) == 5
    assert all(block.shape == (480, 2) for block in captured)


def test_fake_mic_hears_delayed_output() -> None:
    world = FakeWorld(seed=2)
    backend = FakeBackend(world)
    output = world.add_output(latency_ms=20)
    mic = world.add_mic()
    heard: list[np.ndarray] = []
    output_stream = backend.open_output(
        output, lambda count: np.full((count, 2), 0.5, np.float32), 10
    )
    mic_stream = backend.open_mic(mic, heard.append)
    output_stream.start()
    mic_stream.start()
    world.run(0.1)
    assert any(np.max(block) > 0 for block in heard)


def test_fake_silent_loopback_can_skip_callbacks() -> None:
    world = FakeWorld()
    backend = FakeBackend(world)
    source = world.add_source(signal="silence", no_callbacks_while_silent=True)
    captured: list[np.ndarray] = []
    stream = backend.open_source(source, captured.append, 10)
    stream.start()
    world.run(0.1)
    assert captured == []


def test_fake_device_lists_and_disconnect() -> None:
    world = FakeWorld()
    backend = FakeBackend(world)
    source, output, mic = world.add_source(), world.add_output(), world.add_mic()
    assert backend.list_sources() == [source]
    assert backend.list_outputs() == [output]
    assert backend.list_mics() == [mic]
    backend.disconnect(output)
