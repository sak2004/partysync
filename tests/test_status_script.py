"""Tests for scripts/status.py (the progress tracker)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "status.py"

SAMPLE = {
    "project": "Test",
    "updated": "2000-01-01",
    "milestones": [
        {"id": "M1", "title": "First", "state": "todo", "expected": "Does | things", "note": ""},
        {"id": "M2", "title": "Second", "state": "done", "expected": "More", "note": "ok"},
    ],
    "hardware_checks": [{"id": "H1", "check": "Plays", "state": "todo", "note": ""}],
}


def _load_module():
    spec = importlib.util.spec_from_file_location("status_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    module = _load_module()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "status.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Title\n\nintro\n\n<!-- STATUS:START -->\nstale\n<!-- STATUS:END -->\n\noutro\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "STATUS", tmp_path / "docs" / "status.json")
    monkeypatch.setattr(module, "README", tmp_path / "README.md")
    return module, tmp_path


def test_check_detects_stale_then_render_fixes(sandbox):
    module, _ = sandbox
    assert module.main(["check"]) == 1
    assert module.main(["render"]) == 0
    assert module.main(["check"]) == 0


def test_render_is_idempotent_and_keeps_surrounding_text(sandbox):
    module, root = sandbox
    module.main(["render"])
    first = (root / "README.md").read_text(encoding="utf-8")
    module.main(["render"])
    assert (root / "README.md").read_text(encoding="utf-8") == first
    assert first.startswith("# Title\n\nintro\n")
    assert first.endswith("\n\noutro\n")


def test_set_updates_json_and_readme(sandbox):
    module, root = sandbox
    assert module.main(["set", "M1", "in-progress", "--note", "working on it"]) == 0
    data = json.loads((root / "docs" / "status.json").read_text(encoding="utf-8"))
    assert data["milestones"][0]["state"] == "in-progress"
    assert data["milestones"][0]["note"] == "working on it"
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "**IN PROGRESS**" in readme
    assert "1 of 2 milestones done" in readme
    assert module.main(["check"]) == 0


def test_hw_result_is_recorded(sandbox):
    module, root = sandbox
    assert module.main(["hw", "H1", "pass", "--note", "tested"]) == 0
    assert "**PASS**" in (root / "README.md").read_text(encoding="utf-8")


def test_pipe_characters_do_not_break_the_table(sandbox):
    module, root = sandbox
    module.main(["render"])
    assert "Does \\| things" in (root / "README.md").read_text(encoding="utf-8")


def test_unknown_id_exits_with_message(sandbox):
    module, _ = sandbox
    with pytest.raises(SystemExit) as exc:
        module.main(["set", "M99", "done"])
    assert "Unknown milestone id" in str(exc.value)


def test_missing_markers_exit_with_message(sandbox):
    module, root = sandbox
    (root / "README.md").write_text("no markers here\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        module.main(["render"])
    assert "markers" in str(exc.value)


def test_real_repo_readme_is_in_sync():
    module = _load_module()
    assert module.main(["check"]) == 0
