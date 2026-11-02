"""Smoke tests for the GUI package — headless, no display required."""
from __future__ import annotations


def test_gui_app_importable() -> None:
    """src/partysync/gui/app.py must be importable without a display."""
    from partysync.gui import app  # noqa: F401

    assert app is not None


def test_gui_widgets_importable() -> None:
    """src/partysync/gui/widgets.py must be importable without a display."""
    from partysync.gui import widgets  # noqa: F401

    assert widgets is not None


def test_create_app_returns_flask_instance() -> None:
    """create_app() from app_flask must return a Flask application object."""
    from partysync.gui.app import create_app

    flask_app = create_app()
    assert flask_app is not None
    # Verify it quacks like a Flask app (has a test_client method).
    assert callable(getattr(flask_app, "test_client", None))


def test_flask_app_index_route() -> None:
    """The Flask app's root route must return HTTP 200."""
    from partysync.gui.app import create_app

    flask_app = create_app()
    client = flask_app.test_client()
    response = client.get("/")
    assert response.status_code == 200
