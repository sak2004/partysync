"""Entry point for ``python -m partysync``.

Running without a sub-command launches the Flask web dashboard (same as
``python -m partysync gui``).  Pass ``--fake`` to use FakeBackend so the
dashboard works on any OS without audio hardware.
"""
from __future__ import annotations

from partysync.cli import main

raise SystemExit(main())
