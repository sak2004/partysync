"""Command-line device inspection and simulated routing."""
from __future__ import annotations
import argparse
from partysync.backends.fake import FakeBackend, FakeWorld
from partysync.engine import Engine
def fake_backend() -> FakeBackend:
    """Create an out-of-box simulated PartySync setup."""
    world=FakeWorld(); world.add_source("VB-Audio Virtual Cable"); world.add_output("JBL Flip 7 Stereo", latency_ms=120); world.add_output("JBL Charge 4 Stereo", latency_ms=258.5); world.add_mic("Laptop Mic")
    return FakeBackend(world)
def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    parser=argparse.ArgumentParser(); parser.add_argument("command", nargs="?", default="devices", choices=["devices","run"]); parser.add_argument("--fake", action="store_true"); args=parser.parse_args(argv)
    backend=fake_backend()
    if args.command=="devices":
        for device in backend.list_sources()+backend.list_outputs()+backend.list_mics(): print(f"{device.index}: {device.kind:6} {device.name} ({device.default_rate} Hz)")
        return 0
    engine=Engine(backend); engine.start(backend.list_sources()[0], *backend.list_outputs()[:2]); backend.world.run(1); print(engine.stats()); engine.stop(); return 0
