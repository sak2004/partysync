"""Optional Streamlit PartySync dashboard."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
import streamlit as st
from partysync.cli import fake_backend
from partysync.engine import Engine
@st.cache_resource
def engine() -> tuple[Engine, object]:
    """Return a persistent simulated engine."""
    backend=fake_backend(); return Engine(backend),backend
st.title("PartySync Web"); active, backend=engine()
if st.button("Start") and not active.running: active.start(backend.list_sources()[0],*backend.list_outputs()[:2])
st.json(active.stats().__dict__)
