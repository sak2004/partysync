from __future__ import annotations

import sys

import pytest

from partysync.backends.base import BackendUnavailable
from partysync.backends.wasapi import WasapiBackend


def test_wasapi_module_imports_without_windows_audio() -> None:
    if sys.platform != "win32":
        with pytest.raises(BackendUnavailable):
            WasapiBackend()
