# AGENTS.md: standing rules for PartySync

Read `CODEX_PROMPT.md` for the full specification and `README.md` for current status. This file is the short version of the rules that apply to every task.

## What this project is
A Windows desktop app (Python 3.11+) that captures system audio and plays it on two Bluetooth speakers with a per-speaker delay, drift control and microphone-based auto-calibration. Core logic is hardware-independent and fully testable on Linux, macOS and Windows. Only `src/partysync/backends/wasapi.py` touches real audio.

## Workflow
1. Work on the milestone(s) you were asked for, in order (M1 to M8, see `docs/status.json`), one branch each. Do not start a milestone you were not asked for. Merge each finished milestone into `main` with `git merge --no-ff` before starting the next.
2. Create a branch named for the milestone (`m1-core-dsp`).
3. Run `python scripts/status.py set <ID> in-progress` before you start.
4. Commit in small steps using `type(scope): summary` (feat, fix, docs, test, refactor, perf, build, ci, chore, style, revert). The hooks enforce this.
5. Finish with the full test run, then `python scripts/status.py set <ID> done --note "..."`. If anything depends on real Windows audio, use `needs-hw-test` instead of `done`.
6. Never edit the README status tables by hand. Change `docs/status.json` through `scripts/status.py` only.

## Commands
```
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python scripts/status.py check
```

## Hard rules
- Never claim something works on real hardware unless a hardware check was recorded as `pass` by the user. You cannot verify Bluetooth or WASAPI behaviour from a Linux sandbox. Say so in `docs/NOTES.md`.
- Audio callbacks: no logging, no file or network I/O, no GUI calls, no locks held for long, no unbounded allocation. Never let an exception escape a callback.
- No `time.sleep` in the audio path. Timing comes from sample counts.
- `src/partysync/core/` must not import any OS or audio library. Only numpy and soxr.
- Platform-specific dependencies carry environment markers (`PyAudioWPatch; sys_platform == "win32"`).
- Test signals: peak at most -6 dBFS with at least 20 ms fades. Output is hard-clipped to the range -1 to 1 as a last step.
- If the spec is wrong or impossible, record the deviation in `docs/NOTES.md` under "Deviations" and keep going with the best alternative.
- Check package APIs (PyAudioWPatch, soxr) against the installed version instead of guessing from memory.

## Done means
Tests pass, ruff is clean, `python scripts/status.py check` exits 0, the status is updated, and the work is committed.
