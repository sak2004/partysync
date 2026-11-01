# PartySync project checklist

This checklist is a shared, human-readable companion to the authoritative tracker in docs/status.json. Update milestone and hardware-check states only with python scripts/status.py; mark the boxes here as work progresses.

## Current focus

- [x] M1 — Core DSP: completed tests and CI-quality checks; merged to main.

## Build roadmap

- [x] M2 — Audio backends: simulated tests complete; Windows hardware verification remains.
- [ ] M3 — Engine and CLI (later Windows hardware verification)
- [ ] M4 — Auto-calibration (later Windows hardware verification)
- [ ] M5 — Tkinter GUI (later Windows hardware verification)
- [ ] M6 — Packaging and hardware documentation
- [ ] M7 — You run hardware checks H1–H9
- [ ] M8 — Optional stretch goals, only if requested

## Hardware checklist (user-run)

- [ ] H1 — Stereo speaker endpoints appear
- [ ] H2 — Source capture and level meter work
- [ ] H3 — Both speakers play without feedback
- [ ] H4 — 30 minutes without dropouts or crackle
- [ ] H5 — Calibration agrees with by-ear tuning within 10 ms
- [ ] H6 — Laptop microphone calibration works
- [ ] H7 — Delay adjustment is click-free
- [ ] H8 — Remains synchronized after 60 minutes
- [ ] H9 — Speaker reconnection does not crash the app
