from __future__ import annotations

from partysync.cli import fake_backend
from partysync.engine import Engine


def test_simulated_engine_lifecycle_and_controls() -> None:
    backend = fake_backend()
    engine = Engine(backend)
    engine.start(backend.list_sources()[0], *backend.list_outputs()[:2])
    backend.world.run(0.2)
    engine.set_delay_ms("A", 138.5)
    engine.set_gain("B", 0.5)
    engine.set_mode("A", "mono")
    assert engine.stats().running
    assert engine.stats().a["delay_ms"] == 138.5
    engine.stop()
    assert not engine.stats().running
