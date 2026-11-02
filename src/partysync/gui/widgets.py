"""GUI widgets stub — Tkinter replaced by Flask web dashboard.

Since the original Tkinter widgets (SpeakerPanel, LevelMeter) were replaced
by a Flask/HTML5 dashboard at the user's request (see docs/NOTES.md), this
module provides a thin compatibility shim and the public ``launch`` entry point
used by the CLI.
"""
from __future__ import annotations


def launch(fake: bool = False, port: int = 5000) -> None:
    """Start the Flask web dashboard.

    Opens a browser window on Windows and starts the Flask development server.
    On non-Windows platforms the server starts without opening the browser,
    which is useful for headless/CI environments.

    Args:
        fake: If True, use FakeBackend (works on any OS, no audio hardware needed).
        port: TCP port to listen on.
    """
    # Local import so the module is importable headlessly without Flask installed.
    from partysync.gui.app import run

    run(fake=fake, port=port)
