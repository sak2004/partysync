"""GUI app module — launches the Flask web dashboard.

On Windows this opens the system browser and starts Flask.
With ``fake=True`` the FakeBackend is used, making it runnable on any OS.
The module is safe to import headlessly (no display required at import time).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running the module directly from the repo root without installation.
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))


def create_app():
    """Return the Flask application instance.

    Delegates to ``app_flask.create_app`` so the single dashboard
    implementation is not duplicated.
    """
    # Import at call time so the module itself is importable headlessly even
    # when flask is not installed (smoke tests only need the import to succeed).
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "app_flask",
            _repo_root / "app_flask.py",
        )
        if spec is None or spec.loader is None:
            raise ImportError("Cannot locate app_flask.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod.create_app()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Could not load Flask app from app_flask.py: {exc}") from exc


def run(fake: bool = False, port: int = 5000, host: str = "127.0.0.1") -> None:
    """Start the Flask dashboard and (on Windows) open the browser.

    Args:
        fake: If True, use FakeBackend instead of real WASAPI.
        port: TCP port to bind Flask to.
        host: Host address to bind Flask to.
    """
    import webbrowser

    flask_app = create_app()

    if sys.platform == "win32":  # pragma: no cover
        webbrowser.open(f"http://{host}:{port}/")

    flask_app.run(host=host, port=port, debug=False)
