# PartySync

Play one audio stream from a Windows laptop on two different Bluetooth speakers at the same time, in sync, even when the speakers cannot link to each other.

Built for this exact problem: a **JBL Flip 7** (links over Auracast only) and a **JBL Charge 4** (links over PartyBoost only). They cannot talk to each other, so the laptop does the work instead.

## How it works

```
 Windows apps (Spotify, YouTube, VLC ...)
        |  default output = a virtual cable (e.g. "CABLE Input")
        v
 +--------------------+
 |  Source capture    |   WASAPI capture of the virtual cable
 +---------+----------+
           |  float32 stereo, source sample rate
     +-----+-------------------------+
     v                               v
 +--------------+               +--------------+
 | Channel A    |               | Channel B    |   per speaker:
 | resample     |               | resample     |   - resample to device rate
 | ring buffer  |               | ring buffer  |   - delay (ms) + drift control
 | delay + gain |               | delay + gain |   - gain / mute / channel mode
 +------+-------+               +------+-------+
        v  WASAPI render               v  WASAPI render
   JBL Flip 7 (Bluetooth)         JBL Charge 4 (Bluetooth or AUX cable)

 Calibration only:  laptop mic hears a chirp from each speaker in turn,
                    the app measures how much later one speaker is
                    and delays the faster one to match.
```

Three ideas make it work:

1. **Capture** everything the laptop plays and feed it to two output devices.
2. **Delay each speaker separately** (Bluetooth speakers differ by 50 to 300 ms) and keep the three audio clocks from drifting apart.
3. **Calibrate automatically** by timing a test chirp through each speaker with the laptop microphone.

Limits worth knowing: this is for music. Bluetooth plus buffering adds roughly 150 to 400 ms, so video will look out of sync unless your player has an audio-delay setting.

## Project status

This section is generated from `docs/status.json`. Do not edit it by hand.

<!-- STATUS:START -->
**Progress:** 2 of 9 milestones done, 0 of 9 hardware checks passed (last update 2026-11-01).

### Milestones

| ID | Milestone | Status | What is expected | Notes |
|----|-----------|--------|------------------|-------|
| M0 | Repo scaffold and version control | **DONE** | Git hooks, setup scripts, status tracker, README, AGENTS.md and CODEX_PROMPT.md are in the repo. | Scaffolded before any app code exists. |
| M1 | Core DSP (no audio hardware needed) | **DONE** | core/: OutputChannel (ring buffer, delay, drift control, crossfade jump, gain), chirp + matched-filter estimator, resampler wrapper, channel-mode mixing, CI workflow. Unit tests green on Linux and Windows. | Core DSP, unit tests, CI workflow, and shared TODO checklist complete |
| M2 | Audio backends | **NEEDS HW TEST** | backends/: AudioBackend interface, FakeBackend (virtual clocks, latencies, mic) and WasapiBackend (PyAudioWPatch: device listing, source capture, 2 render streams, mic capture). | Fake backend tests pass; WASAPI adapter needs Windows audio verification |
| M3 | Engine and CLI | **TODO** | Engine wiring (source -> per-output resample -> OutputChannel -> render), keep-alive, idle-source handling, CLI devices/run. 10-minute simulated drift test passes. | - |
| M4 | Auto-calibration | **TODO** | Calibration state machine and CLI calibrate. Simulated error under 1 ms across the test matrix; clear failure reasons (silent mic, dead speaker, low SNR). | - |
| M5 | Tkinter GUI | **TODO** | Device pickers, per-speaker volume/mute/delay/mode, Start/Stop, Calibrate with progress, level meters, status bar, saved settings. | - |
| M6 | Packaging and hardware docs | **TODO** | PyInstaller build script, docs/HARDWARE_TEST.md, docs/NOTES.md (unverified Windows assumptions), README usage section finished. | - |
| M7 | Real-hardware verification | **TODO** | You run H1-H9 on the Windows laptop with the Flip 7 and Charge 4 and record results with status.py hw. | Only you can do this one. |
| M8 | Stretch goals (optional) | **TODO** | N speakers, auto-reconnect on Bluetooth drop, tap-to-nudge sync, saved presets per speaker pair. | - |

### Hardware checks (only you can run these on the real speakers)

| ID | Check | Status | Notes |
|----|-------|--------|-------|
| H1 | Both speakers show up as outputs, using the Stereo endpoint (not Hands-Free). | **TODO** | - |
| H2 | Source capture works (virtual cable or chosen loopback) and the level meter moves. | **TODO** | - |
| H3 | Audio plays on both speakers at once with no feedback loop. | **TODO** | - |
| H4 | 30 minutes of playback with no dropouts or crackle. | **TODO** | - |
| H5 | Calibration succeeds in a quiet room and agrees with by-ear tuning within 10 ms. | **TODO** | - |
| H6 | Calibration works with the laptop mic (if it fails, try disabling mic enhancements/echo cancellation). | **TODO** | - |
| H7 | Moving the delay slider is click-free. | **TODO** | - |
| H8 | Still in sync after 60 minutes (listen with a click track). | **TODO** | - |
| H9 | Turning a speaker off and on does not crash the app. | **TODO** | - |
<!-- STATUS:END -->

### Updating the status

```
python scripts/status.py show                                   # print the table in the terminal
python scripts/status.py set M1 in-progress --note "started"    # milestone state: todo, in-progress, needs-hw-test, done, blocked
python scripts/status.py set M1 done --tag                      # also creates git tag milestone-M1
python scripts/status.py hw H3 pass --note "30 min, no dropouts"  # hardware check: todo, pass, fail
python scripts/status.py render                                 # rewrite the tables above
python scripts/status.py check                                  # exits 1 if the README is stale (the pre-commit hook runs this)
```

`needs-hw-test` means the code and simulated tests are finished but the behaviour depends on real Windows audio or the real speakers. Only a hardware check (H1 to H9) moves it forward.

## Building it with Codex

1. **From nothing:** open Codex in an empty folder and paste `CODEX_BOOTSTRAP_PROMPT.md`. Codex creates this whole repo itself (files, Git, hooks, status tracker) and then builds milestones M1 to M6 in order, one branch each, merged into `main`.
2. **Later sessions (repo already exists):** tell Codex `Read CODEX_PROMPT.md, AGENTS.md and README.md, then continue with the next milestone that is TODO.`
3. If a run stops early, it stops at a milestone boundary. Check the status table above to see where it got to.
4. After M6, run through `docs/HARDWARE_TEST.md` with the real speakers and record each result with `status.py hw`.

If you already have this folder on your machine, run the Git setup once (see below) instead of step 1.

## Version control

One-time setup, from the project folder:

```
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\setup_git.ps1

# Git Bash / macOS / Linux
sh scripts/setup_git.sh
```

This initialises the repo on `main`, turns on the hooks in `.githooks/`, sets the commit template, and makes the first commit and tags (`v0.0.0`, `milestone-M0`). It never rewrites an existing repo.

Workflow:

| Rule | Detail |
|------|--------|
| Branches | `main` always works. One branch per milestone: `m1-core-dsp`, `m2-backends`, and so on. |
| Commits | `type(scope): summary` (feat, fix, docs, test, refactor, perf, build, ci, chore, style, revert). The `commit-msg` hook rejects anything else. |
| Before each commit | The `pre-commit` hook checks the README status tables are current and runs `pytest`. Skip tests for a WIP commit with `SKIP_TESTS=1`. |
| Finishing a milestone | `python scripts/status.py set M1 done --tag`, commit, merge to `main` with `git merge --no-ff m1-core-dsp`. |
| Remote (optional) | `git remote add origin <url>` then `git push -u origin main --tags`. |

## Windows audio setup (needed from M3 on)

1. Install a virtual audio cable, such as the free VB-Audio Virtual Cable (Voicemeeter's virtual input also works).
2. In Windows Sound settings, set **CABLE Input** as the default playback device. Everything you play now goes into the cable.
3. Pair both speakers in Bluetooth settings. In PartySync, pick the **Stereo** entry for each speaker, not **Hands-Free**.
4. In PartySync, choose the cable as the source and the two speakers as outputs, then press Start.

The source must never be one of the two speaker outputs, or you get a feedback loop.

A wired output works too. If you plug the Charge 4's AUX cable into the laptop, it shows up as a normal output device and has almost no latency, which makes calibration easier.

## Troubleshooting

| Problem | Likely cause and fix |
|---------|----------------------|
| Sound is muffled and thin | You picked the Hands-Free Bluetooth profile. Use the Stereo endpoint. |
| Crackling or dropouts | Two Bluetooth streams from one laptop radio is a lot. Wire one speaker (AUX or USB), or move the laptop closer. |
| Echo or doubling | Delays are not matched yet. Run Calibrate, then fine-tune with the delay buttons. |
| Calibration cannot find the chirps | Quiet room, laptop near the listening spot, speakers at party volume. Turn off mic enhancements and echo cancellation for the laptop mic in Windows sound settings, and allow microphone access for desktop apps. |
| Loud howl | The source is one of the output devices. Choose the virtual cable as the source. |
| One speaker goes silent after a while | The speaker went to standby or dropped the connection. Turn it on again and press Start. |

## Repository layout

```
CODEX_PROMPT.md      full build specification for Codex
AGENTS.md            standing rules Codex reads automatically
docs/status.json     source of truth for the status tables
docs/NOTES.md        assumptions and decisions (written by Codex)
docs/HARDWARE_TEST.md  the checks you run on real hardware (written by Codex)
scripts/             status.py, setup_git.sh, setup_git.ps1 (and the exe build script from M6)
.githooks/           pre-commit and commit-msg hooks
src/partysync/       the app (built in M1 to M5)
tests/               pytest suite, runs without audio hardware
```
