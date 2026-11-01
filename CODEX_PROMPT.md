# PartySync: build instructions for Codex

How to use this file: give Codex the repo and say
`Read CODEX_PROMPT.md, AGENTS.md and README.md, then build milestone M1 only.`
Repeat with M2, M3 and so on. One milestone per run.

---

## 0. Your job

Build **PartySync**, a Windows desktop app in Python that captures the laptop's system audio and plays it on **two different Bluetooth speakers at the same time, in sync**. Each speaker gets its own volume, mute, channel mode and delay, and the app can **auto-calibrate** the delays by playing a chirp through each speaker and timing it with the laptop microphone.

The scaffold (git hooks, status tracker, README, AGENTS.md) already exists. Do not rewrite it. Work milestone by milestone (section 10), update status with `scripts/status.py`, and obey the rules in section 11.

## 1. Why this exists

The user owns a JBL Flip 7 and a friend owns a JBL Charge 4. The Flip 7 only links with other speakers over Auracast. The Charge 4 only does PartyBoost. They cannot link, so a phone app cannot fix it. The laptop can: it plays the same audio to two output devices, and the app aligns them in time.

Non-goals (do not build): Bluetooth pairing code, Auracast or PartyBoost support, BLE, a phone app, a driver, changing the Windows default device, anything needing administrator rights, streaming-service integration.

## 2. Fixed technical decisions

| Topic | Decision |
|-------|----------|
| Language | Python 3.11+ (test on 3.11 and 3.12) |
| Target OS | Windows 10/11. Core and tests must also run on Linux (CI and Codex sandbox). |
| Audio I/O | `PyAudioWPatch` (import name `pyaudiowpatch`), WASAPI shared mode, callback streams. Windows only. |
| Math | `numpy` only. No scipy. |
| Resampling | `soxr` streaming resampler (`soxr.ResampleStream`). Verify the API against the installed version. |
| GUI | Tkinter with ttk (standard library) |
| Tests | `pytest`, `ruff` |
| Packaging | PyInstaller one-file `PartySync.exe` (M6) |
| Source of audio | A virtual audio cable is the recommended source (user sets it as the Windows default output, the app captures it). Any WASAPI loopback or capture device can be chosen. |
| Sample rates | No global internal rate. Each channel resamples from the source rate to its own device rate. |
| Sample format | float32, interleaved stereo inside the app. Convert at the device boundary. |

`requirements.txt`:
```
numpy>=1.26
soxr>=0.5
PyAudioWPatch>=0.2.12; sys_platform == "win32"
```
`requirements-dev.txt`: `pytest>=8`, `ruff`, `pyinstaller` (the last one with `; sys_platform == "win32"`).

## 3. Repository layout to create

```
pyproject.toml                 # package metadata, pytest config (testpaths=tests), ruff config (line length 100)
requirements.txt
requirements-dev.txt
.github/workflows/ci.yml       # pytest + ruff on ubuntu-latest and windows-latest, Python 3.11 and 3.12
src/partysync/
  __init__.py                  # __version__
  __main__.py                  # calls cli.main()
  cli.py                       # section 5.7
  config.py                    # settings load/save (section 5.9)
  logging_setup.py
  engine.py                    # section 5.5
  calibration.py               # section 5.6
  core/                        # NO OS or audio imports here
    __init__.py
    constants.py
    output_channel.py          # section 5.2
    chirp.py                   # section 5.3
    resample.py                # StreamResampler wrapper over soxr
    mixing.py                  # channel modes, down/up-mix, clip
    stats.py                   # dataclasses for stats
  backends/
    __init__.py
    base.py                    # DeviceInfo, protocols (section 5.4)
    fake.py                    # simulated devices for tests
    wasapi.py                  # real Windows backend
  gui/
    __init__.py
    app.py                     # main window (section 5.8)
    widgets.py                 # SpeakerPanel, LevelMeter
tests/                         # section 7
scripts/build_exe.ps1          # M6
docs/NOTES.md                  # assumptions, decisions, deviations
docs/HARDWARE_TEST.md          # M6
```

## 4. Data model

```python
@dataclass(frozen=True)
class DeviceInfo:
    index: int                 # backend-specific id
    name: str                  # name as shown to the user
    kind: Literal["source", "output", "mic"]
    channels: int
    default_rate: int
    is_loopback: bool = False
    warning: str | None = None # e.g. "Hands-Free profile: low quality"

class ChannelMode(Enum):       # which part of the stereo source this speaker plays
    STEREO = "stereo"          # L and R
    MONO = "mono"              # (L+R)/2 on every output channel
    LEFT = "left"              # L on every output channel
    RIGHT = "right"            # R on every output channel
```

## 5. Module specifications

### 5.1 Constants (`core/constants.py`)

```
BLOCK_MS            = 10      # preferred capture/render block
SAFETY_MS           = 60      # minimum buffered audio per channel (absorbs callback jitter)
MAX_DELAY_MS        = 1000
RING_SECONDS        = 4.0
JUMP_MS_MIN         = 25      # gross error threshold (see 5.2); real threshold is max(JUMP_MS_MIN, 3 * largest block)
SLIP_DEADBAND_MS    = 1.0
CROSSFADE_MS        = 5
GAIN_RAMP_MS        = 20
FILTER_TAU_S        = 0.5     # smoothing of the fill-level error
IDLE_SOURCE_MS      = 100     # no capture callback for this long = source idle
CHIRP_DUR_S         = 0.4
CHIRP_F0, CHIRP_F1  = 400.0, 7000.0
CHIRP_AMP           = 0.5     # -6 dBFS
CHIRP_FADE_MS       = 20
CAL_GAP_S           = 2.0     # between the two chirps of one round
CAL_WARMUP_S        = 0.5     # mic must run this long before the first chirp
CAL_TAIL_S          = 2.0     # listening time after the last chirp of a round
CAL_ROUNDS          = 3       # order per round: A then B, B then A, A then B
CAL_MIN_PMR         = 8.0     # peak-to-median ratio needed for a detection
CAL_MAX_SPREAD_MS   = 10.0    # max disagreement between rounds
```

### 5.2 `OutputChannel` (`core/output_channel.py`) — the heart of the app

One instance per speaker. It owns a ring buffer at **that device's sample rate**, holds the delay, controls drift, and applies gain.

```python
class OutputChannel:
    def __init__(self, sample_rate: int, channels: int = 2, *, block_hint_frames: int = 480,
                 safety_ms: float = SAFETY_MS, ring_seconds: float = RING_SECONDS) -> None: ...
    # producer side: called from the capture callback (single writer)
    def write(self, frames: np.ndarray) -> None            # shape (n, channels) float32
    def write_silence(self, n: int) -> None
    # consumer side: called from the render callback (single reader)
    def read(self, n: int) -> np.ndarray                   # ALWAYS returns shape (n, channels) float32
    # control side: any thread
    def set_delay_ms(self, ms: float) -> None              # clamped to 0..MAX_DELAY_MS
    def set_gain(self, gain: float) -> None                # linear 0..1.5, ramped over GAIN_RAMP_MS
    def set_muted(self, muted: bool) -> None               # ramped the same way
    def set_source_idle(self, idle: bool) -> None          # see below
    def stats(self) -> ChannelStats
```

`ChannelStats`: `fill_ms`, `target_ms`, `delay_ms`, `underruns`, `overruns`, `jumps`, `slips`, `drift_ppm_estimate`, `primed`, `peak`, `rms`.

Behaviour (implement exactly; this is what makes sync work):

1. **Target fill.** `target_frames = (safety_ms + delay_ms) * rate / 1000`. The delay the user sets is extra buffered audio on top of the safety buffer. Both channels use the same `safety_ms`, so the difference between two channels' delays is exactly the difference of their `delay_ms`.
2. **Ring buffer.** Preallocated numpy array, capacity `ring_seconds * rate` frames. Monotonic integer `write_idx` and `read_idx` (never wrap the counters, only index with modulo). The writer copies data first and publishes `write_idx` last. The reader reads `write_idx` once per `read()` call. This is a single-producer single-consumer queue and needs no lock. If the writer would overwrite unread data, drop the oldest data, advance `read_idx`, and count an overrun.
3. **Priming.** Until `fill >= target_frames` the channel returns silence. When that becomes true, set `read_idx = write_idx - target_frames` and mark primed.
4. **Underrun.** If a `read(n)` would need more data than is available: return what exists padded with silence, set `primed = False`, and count an underrun. If `set_source_idle(True)` is active, do not count it as an underrun (the source is just silent, see 5.5).
5. **Fill error.** `err = fill - target_frames` where `fill = write_idx - read_idx`. Positive means too much buffered (we are late), negative means too little.
6. **Filtered error.** Raw fill jitters by up to one capture block because blocks arrive in bursts. Keep `err_filt` as an exponential moving average of `err` with time constant `FILTER_TAU_S`, updated once per `read()`.
7. **Slip (small corrections, drift).** If `abs(err_filt) > SLIP_DEADBAND_MS` (in frames), consume `n + s` input frames, `s = +1` if `err_filt > 0` else `-1`, and linearly interpolate them down or up to `n` output frames (`np.interp`). One frame per block is at most 0.2 percent speed change at 10 ms blocks, far more than the 50 to 200 ppm of real clock drift, and inaudible (a few cents).
8. **Jump (gross errors, delay changes).** Let `jump = max(JUMP_MS_MIN, 3 * block_ms)`. If the *raw* `abs(err) > jump` frames, crossfade to the correct position: compute the block from the old read position and from `new_pos = write_idx - target_frames`, mix them with a linear ramp over `CROSSFADE_MS` (old to new), continue from `new_pos + n`. Count a jump. After any jump reset `err_filt = 0`.
9. **Delay changes.** `set_delay_ms` only updates the target. Changes of 25 ms or less are followed by slipping, larger ones by a jump. When the target changes, re-seed `err_filt` with the current raw error so slipping starts immediately.
10. **Gain and mute.** Per-block linear ramp from previous gain to new gain across the block so there are no zipper clicks. Muted means gain 0 through the same ramp.
11. `read()` must not allocate large arrays or take locks. Preallocate scratch buffers sized from `block_hint_frames` and grow once if a larger block arrives.
12. `drift_ppm_estimate`: slope of `fill` over the last ~20 seconds converted to ppm. Used only for display.

### 5.3 Chirp and estimator (`core/chirp.py`)

```python
def make_chirp(fs: int, dur_s=CHIRP_DUR_S, f0=CHIRP_F0, f1=CHIRP_F1,
               amp=CHIRP_AMP, fade_ms=CHIRP_FADE_MS) -> np.ndarray   # mono float32, Tukey-style fades

def matched_filter_envelope(rec: np.ndarray, ref: np.ndarray) -> np.ndarray
    # |cross-correlation of rec with the analytic (complex) version of ref|, computed with FFTs.
    # Output index i = the time (in samples) at which ref STARTS inside rec. Length len(rec)-len(ref)+1.

@dataclass
class Detection:
    t_s: float       # start time of the chirp in the recording, sub-sample (parabolic interpolation of the envelope peak)
    pmr: float       # peak-to-median ratio of the envelope

def find_chirps(rec: np.ndarray, fs: int, ref: np.ndarray, n_expected: int,
                min_sep_s: float = 0.5) -> list[Detection]
    # Greedy: take the highest peak, blank +/- min_sep_s around it, repeat until n_expected found
    # (or no peak with pmr >= 3 is left). Return sorted by time.
```
Use a linear chirp: phase `2*pi*(f0*t + (f1-f0)*t**2/(2*T))`. The analytic reference is built with an FFT (zero the negative frequencies, double the positive ones). Everything vectorised with `np.fft.rfft`/`irfft` or full complex FFT, no Python loops over samples.

### 5.4 Backend interface (`backends/base.py`)

```python
class AudioBackend(Protocol):
    def list_sources(self) -> list[DeviceInfo]: ...   # capture devices incl. loopback ones, excluding mics
    def list_outputs(self) -> list[DeviceInfo]: ...
    def list_mics(self) -> list[DeviceInfo]: ...
    def open_source(self, dev: DeviceInfo, on_frames: Callable[[np.ndarray], None], block_ms: int) -> AudioStream: ...
    def open_output(self, dev: DeviceInfo, render: Callable[[int], np.ndarray], block_ms: int) -> AudioStream: ...
    def open_mic(self, dev: DeviceInfo, on_frames: Callable[[np.ndarray], None]) -> AudioStream: ...

class AudioStream(Protocol):
    sample_rate: int
    channels: int
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
```
`on_frames` receives `(n, channels)` float32. `render(n)` must return `(n, channels)` float32.

**`FakeBackend` (`backends/fake.py`)** is what makes everything testable without hardware. It is a deterministic simulation with a virtual clock, no threads, no sleeping:
- `FakeWorld(seed)` holds virtual time and a list of devices. `world.run(seconds)` advances time and fires callbacks in time order.
- A fake source device: configurable rate (44100 or 48000), clock skew in ppm, block size, optional jitter in callback timing, a programmable signal (sine, noise, click track, or silence with optional "no callbacks while silent" mode that imitates WASAPI loopback).
- A fake output device: rate, clock skew in ppm, **output latency in ms** (the time between the render callback and sound in the air), block size, can be "disconnected" mid-run.
- A fake mic: rate, clock skew, noise level (SNR), optional room reverb (a few attenuated echoes), hears the sum of all fake outputs after their latency plus a small per-speaker acoustic delay. Implementation can be offline-style (accumulate each output's samples with their latency into a timeline and let the mic read from it).
- Engine code must work identically against `FakeBackend` and `WasapiBackend`.

**`WasapiBackend` (`backends/wasapi.py`)** (Windows only; guard the import so the module imports fine elsewhere and raises `BackendUnavailable` when used):
- Use `get_host_api_info_by_type(pyaudio.paWASAPI)`. List **only WASAPI host-API devices** (MME, DirectSound and WDM-KS duplicates are noise).
- Loopback devices come from `get_loopback_device_info_generator()`; they have `isLoopbackDevice == True`. Name shown to the user: strip the "[Loopback]" suffix only for display and keep a "loopback" flag.
- Outputs: `maxOutputChannels > 0`, not loopback. Flag names containing "Hands-Free" or "Headset" with `warning="Hands-Free profile: low quality, use the Stereo entry"` and sort them last.
- Mics: `maxInputChannels > 0`, not loopback.
- Open every stream with the device's `defaultSampleRate` and `min(2, channels)` channels (use the device's own channel count for the open call if WASAPI refuses fewer; convert to stereo yourself). `frames_per_buffer = rate * block_ms // 1000`. Use callback mode. If opening fails with an invalid-sample-rate error, retry once with the other of 48000/44100 and log it.
- Callbacks: convert the int16 or float32 bytes to float32 with `np.frombuffer`, reshape, convert. Wrap the entire callback body in try/except: on any exception return silence (render) or ignore the block (capture), increment an error counter, return `paContinue`. No logging inside callbacks.
- `stop()` and `close()` must swallow `OSError` (Bluetooth speakers that disconnected raise there).
- Mark everything in this file `# pragma: no cover` and put each uncertain assumption in `docs/NOTES.md` under "Assumptions to verify on Windows".

### 5.5 Engine (`engine.py`)

```python
class Engine:
    def __init__(self, backend: AudioBackend, *, block_ms: int = BLOCK_MS, keepalive: bool = True) -> None: ...
    def start(self, source: DeviceInfo, out_a: DeviceInfo, out_b: DeviceInfo) -> None
    def stop(self) -> None
    # live controls (thread-safe, may be called from the GUI thread)
    def set_delay_ms(self, ch: Literal["A", "B"], ms: float) -> None
    def set_gain(self, ch, gain: float) -> None
    def set_muted(self, ch, muted: bool) -> None
    def set_mode(self, ch, mode: ChannelMode) -> None
    def set_master_gain(self, gain: float) -> None
    def stats(self) -> EngineStats        # per channel ChannelStats + source peak/rms + source_idle + callback error counts + connected flags
    # calibration hooks (used by calibration.py)
    def begin_calibration(self) -> None
    def source_frame_counter(self) -> int
    def schedule_test_signal(self, items: list[TestSignal]) -> None   # TestSignal(channel, start_source_frame, samples at source rate)
    def end_calibration(self) -> None
```
The engine creates no threads of its own. All work happens inside backend callbacks.

Capture callback (`_on_source(frames)`), in this order:
1. Convert to stereo float32 (mono: duplicate; more than 2 channels: use the first two).
2. Update source peak/RMS. Update `last_capture_time` (`time.monotonic()`), clear `source_idle` on all channels.
3. If calibration is active: replace the block with silence, then add any scheduled test samples that fall inside this block's source-frame range (so the chirp enters the pipeline at an exact source frame index). Increment the source frame counter by the block length.
4. For each channel: apply the channel mode, resample source rate to the channel's rate with that channel's own `StreamResampler`, `channel.write(...)`.

Render callback for a channel (`_render(ch, n)`):
1. If `now - last_capture_time > IDLE_SOURCE_MS`, call `channel.set_source_idle(True)` (this is what happens with WASAPI loopback when nothing is playing and no packets arrive).
2. `x = channel.read(n)`; multiply by master gain; hard-clip to -1..1; adapt channel count (mono device: average the two columns); return.

Keep-alive (`keepalive=True`): if the source is a loopback device, also open a render stream of digital silence on the **same endpoint** so Windows keeps delivering loopback packets, and also keep each Bluetooth output stream running continuously (they already are, they render silence while nothing plays). Record in `docs/NOTES.md` that the need for the source keep-alive must be verified on Windows.

Validation in `start()`: raise `ValueError` with a clear message if the source and an output are the same device or the same endpoint (feedback loop), if A and B are the same device, or if a device is missing.

Resilience: if an output stream raises or reports disconnection, mark that channel `connected = False` in the stats, keep the other channel playing, and never crash. (Auto-reconnect is M8.)

### 5.6 Calibration (`calibration.py`)

Goal: find `delta = L_B - L_A`, where `L_X` is the total time from "audio enters the pipeline" to "sound reaches the microphone" for speaker X, then set the delays so both speakers line up.

Only the **difference** matters, so the microphone's own latency and clock offset cancel out. That is why we never need absolute timing. Do not try to measure absolute latency.

Implement as a **state machine driven by callbacks** (no sleeping, no threads in the logic), plus a thin threaded wrapper for the GUI:

```python
@dataclass
class CalibrationResult:
    ok: bool
    reason: str | None          # human readable, e.g. "Speaker B was not heard. Is it connected and loud enough?"
    delta_ms: float | None      # L_B - L_A
    delay_a_ms: float | None
    delay_b_ms: float | None
    spread_ms: float | None
    min_pmr: float | None
    per_round_ms: list[float]

class CalibrationSession:
    def __init__(self, engine: Engine, mic: DeviceInfo, backend: AudioBackend, *, rounds=CAL_ROUNDS) -> None
    def start(self) -> None
    def progress(self) -> tuple[str, float]          # (message, 0..1)
    def result(self) -> CalibrationResult | None     # None until finished
    def cancel(self) -> None
```

Procedure:
1. `engine.begin_calibration()` (program audio is muted, both `delay_ms` are set to 0 so the measurement is taken with equal delays; remember the previous delays so `cancel()` can restore them).
2. Open the mic stream; accumulate mic samples. Use mic channel 0 (or the mean of channels). Work in the mic's own sample rate and its own sample counter.
3. When the mic has delivered at least `CAL_WARMUP_S` of audio, schedule the whole test plan at once, relative to the engine's current source frame counter plus a 0.3 s margin. Round `k` starts at `T0 + k * R` where `R = CAL_WARMUP_S + CHIRP_DUR_S + CAL_GAP_S + CHIRP_DUR_S + CAL_TAIL_S`. In each round the first speaker plays the chirp at the round start and the second speaker plays it `CAL_GAP_S + CHIRP_DUR_S` later. Order per round: A then B, B then A, A then B. The chirp is generated at the source sample rate and goes into the same pipeline as program audio (resample, ring buffer, device), so the measurement includes everything the real audio goes through.
4. After the last round plus `CAL_TAIL_S`, stop. Run `find_chirps(mic_recording, mic_rate, ref_at_mic_rate, 2 * rounds)`. The reference for the matched filter is the chirp generated at the mic's rate.
5. If fewer than `2 * rounds` chirps are found, fail. Work out which speaker is missing from the pattern and name it in `reason`. If every detection is missing, say the mic heard nothing and suggest checking microphone permission and mic enhancements.
6. For each round: `d = (t_second - t_first) - (CAL_GAP_S + CHIRP_DUR_S)` is `L_second - L_first`. Convert to `L_B - L_A` (negate when B played first). `delta_ms` is the **median** over rounds; `spread_ms` is max minus min.
7. Fail (with a specific reason) if any detection has `pmr < CAL_MIN_PMR` ("too quiet or too noisy: raise the speaker volume, move the laptop closer, quiet the room") or `spread_ms > CAL_MAX_SPREAD_MS` ("measurements disagree, try again").
8. On success: if `delta_ms > 0` (B slower) then `delay_a = delta_ms, delay_b = 0`, otherwise `delay_a = 0, delay_b = -delta_ms`. If either exceeds `MAX_DELAY_MS`, fail. Call `engine.end_calibration()` which restores program audio and applies the new delays.
9. Total duration is about 20 seconds. The GUI warns the user that they will hear loud sweeps.

### 5.7 CLI (`cli.py`, run as `python -m partysync ...`)

```
python -m partysync                      # opens the GUI (same as `gui`)
python -m partysync devices              # table of sources, outputs, mics with index, name, rate, flags, warnings
python -m partysync run --source S --a A --b B [--delay-a MS] [--delay-b MS] [--gain-a G] [--gain-b G]
python -m partysync calibrate --source S --a A --b B --mic M [--apply]
```
`S`, `A`, `B`, `M` accept a device index or a case-insensitive substring of the name; an ambiguous or unknown match prints the candidates and exits with code 2. `run` prints one status line per second (per channel: fill ms, delay ms, underruns, jumps, drift ppm, plus source level) and stops on Ctrl+C. Exit codes: 0 ok, 1 runtime failure, 2 usage error.

### 5.8 GUI (`gui/app.py`, `gui/widgets.py`)

Tkinter + ttk, Segoe UI font, minimum window 760x520, scales with DPI (call `ctypes.windll.shcore.SetProcessDpiAwareness(1)` on Windows, guarded).

Layout:
- **Top bar:** Source dropdown, a Refresh button, Start/Stop button (shows state).
- **Two speaker panels side by side** ("Speaker A" and "Speaker B"), each with: an editable nickname label, device dropdown (Hands-Free entries marked and sorted last), volume slider 0..100 percent, Mute checkbox, channel-mode dropdown (Stereo, Mono, Left, Right), delay slider 0..1000 ms with a numeric entry and `-1`, `+1`, `-10`, `+10` buttons, and a level meter (peak bar with a short hold marker).
- **Calibration strip:** microphone dropdown, Calibrate button, progress bar, result text such as "Charge 4 is 148.3 ms slower. Delaying Flip 7 by 148 ms." and a Reset delays button.
- **Status bar:** per speaker `fill / delay / underruns / drift ppm`, source level, and a "source idle" indicator.
- Before calibrating, show a confirm dialog: "You will hear loud sweeps for about 20 seconds. Put the laptop where people will listen, keep the room quiet, set the speakers to party volume. Continue?"
- Threading: the engine runs in backend callbacks, calibration in a worker thread. The GUI never blocks. Engine to GUI updates go through a `queue.Queue` polled with `after(100, ...)`. GUI to engine calls use the thread-safe setters.
- Start/Stop disables the device dropdowns while running. Calibrate is disabled unless running and a mic is selected.
- Errors (feedback loop, device missing, stream failed) appear in a message box with a plain-language explanation, never a traceback.
- A "Copy diagnostics" button copies: app version, Python version, device table, selected devices, rates, per-channel stats, last calibration result, last 50 log lines.

### 5.9 Settings and logging

- Settings file `%LOCALAPPDATA%\PartySync\config.json` (fallback `~/.partysync/config.json` on other OSes). Keys: last source/outputs/mic (by name, not index), nicknames, per-device volume, delay, mode, mute, window size. Load failures must never crash the app (fall back to defaults and log).
- Remember delays **per speaker pair** (key = sorted pair of device names) so the same two speakers come back aligned.
- Logging: `logging` with a rotating file handler (1 MB, 3 files) in `%LOCALAPPDATA%\PartySync\logs\`. Log device lists, chosen rates, calibration results, stream errors. Never log from audio callbacks.

## 6. Windows pitfalls to handle or document

1. Bluetooth speakers expose two endpoints: "Stereo" (A2DP, good) and "Hands-Free" (headset, bad). Default to Stereo and warn on Hands-Free.
2. The same physical device appears once per host API. List WASAPI only.
3. WASAPI loopback may deliver **no packets while nothing is playing**. The engine must treat this as an idle source, not as an error, and the keep-alive stream is the fix to verify.
4. Shared-mode streams must use the endpoint's mix format (rate, channels). Do not assume 44.1 or 48 kHz; the two speakers may differ.
5. Laptop microphones often have echo cancellation or noise suppression that removes the played chirps. If calibration reports a missing or weak chirp, the reason text must mention this and how to turn it off.
6. Microphone permission: Windows can block desktop apps from the mic. Mention it in the failure reason when the mic recording is silent (all zeros).
7. Bluetooth latency is not constant across reconnects, so calibrate again after reconnecting.
8. Do not select the same endpoint as source and output (feedback). Validate it.
9. Callbacks run on PortAudio threads. Treat them as real time (see AGENTS.md hard rules).

## 7. Tests (pytest, no audio hardware, whole suite under 60 seconds)

All timing in tests uses virtual time via `FakeWorld`. No `time.sleep`.

`tests/test_output_channel.py`
- Fixed delay: write an impulse at frame 0 of a stream, read it out; with `delay_ms = D`, the impulse appears `safety + D` ms after it was written, within 1 frame.
- Drift: writer at `rate * (1 + 150e-6)`, reader at `rate`, 10 virtual minutes, both ways (`-150 ppm` too). No underruns, no overruns, `abs(fill - target)` stays under the jump threshold, jumps == 0, slips > 0.
- Callback jitter: writer blocks of 480 frames with +/-3 ms arrival jitter, reader blocks of 441 frames. No underruns with `safety_ms = 60`.
- Delay change 40 ms to 300 ms and back during a 440 Hz sine of amplitude 0.5: the largest sample-to-sample step stays under 0.2, the settled delay is within 1 ms of the target after one second.
- Underrun recovery: stop the writer for 500 ms, restart it, output is silence during the gap then audio again, exactly one underrun counted, correct delay restored. With `set_source_idle(True)` no underrun is counted.
- Gain ramp: step the gain from 1 to 0 on a sine, largest step under 0.1.

`tests/test_chirp.py`
- `find_chirps` recovers chirp start times to within 0.05 ms for random delays (0 to 1.5 s, fractional samples), at 0 dB, 10 dB and 20 dB SNR, with a 3-tap reverb, and with a mic clock error of +/-200 ppm.
- Detects exactly `n_expected` chirps and reports `pmr` above `CAL_MIN_PMR` in those cases; returns fewer detections (and low `pmr`) on pure noise.

`tests/test_calibration.py` (uses `FakeWorld`)
- Matrix of 20 random cases: speaker latencies in 20..450 ms, source rates 44100 or 48000, output rates 44100 or 48000 (different per speaker), clock skews up to +/-150 ppm, mic SNR 5..25 dB, small reverb. `abs(measured delta - true delta) < 1.0 ms` in every case.
- After applying the result, play an impulse through the simulated pipeline and check the two outputs reach the mic within 1.5 ms of each other.
- Failure cases return `ok == False` with the right reason: silent mic, one speaker disconnected (names the right speaker), very noisy room, mic that mutes during the test.
- `cancel()` restores the previous delays and program audio.

`tests/test_engine.py` (uses `FakeWorld`)
- 10 virtual minutes end to end with three different clock skews (source, A, B). No underruns, no crashes, the two outputs stay aligned within 1.5 ms of the configured delay difference.
- Idle source (no callbacks for 5 s) then audio resumes: no underrun count, audio resumes with correct relative delay.
- Feedback-loop validation raises `ValueError`.
- Disconnecting one fake output mid-run leaves the other playing and flags the stats.

`tests/test_cli.py`: device matching (index, substring, ambiguous, unknown) and `devices` output against `FakeBackend`.
`tests/test_config.py`: round trip, corrupt file falls back to defaults, per-pair delay memory.
`tests/test_status_script.py` already exists.

CI (`.github/workflows/ci.yml`): checkout, setup-python (3.11, 3.12), install requirements, `ruff check .`, `pytest -q`, on both `ubuntu-latest` and `windows-latest`. On Windows the real `PyAudioWPatch` install must succeed even though no audio device is present.

## 8. Packaging (M6)

`scripts/build_exe.ps1`: creates a venv, installs requirements, runs PyInstaller with `--noconsole --onefile --name PartySync`, collects the PyAudioWPatch binaries (`--collect-all pyaudiowpatch` or hidden imports as needed, verify), and prints the path to `dist\PartySync.exe`. Commit the generated `.spec` file. State in `docs/NOTES.md` that the exe was not run on Windows if you could not.

## 9. Documents you must write

- `docs/NOTES.md` with three sections: **Decisions** (why you chose X), **Deviations** (where you departed from this spec and why), **Assumptions to verify on Windows** (every WASAPI or Bluetooth behaviour you could not test).
- `docs/HARDWARE_TEST.md` (M6): for each of H1 to H9 in `docs/status.json`, numbered steps the user follows with a Flip 7 and a Charge 4, what a pass looks like, what to copy into a bug report (use "Copy diagnostics"), and the exact `python scripts/status.py hw Hn pass|fail --note "..."` command to record the result. Include how to listen for sync with a click track and how to check by ear within 10 ms (play a metronome at 120 bpm and listen for flams).
- Finish the README "Windows audio setup" section with real commands once the CLI exists. Do not edit the status tables by hand.

## 10. Milestones and acceptance criteria

Work on one at a time. Status ids match `docs/status.json`.

| ID | Scope | Done when |
|----|-------|-----------|
| M1 | `pyproject.toml`, requirements, CI workflow, everything in `core/` (5.1, 5.2, 5.3, resampler, mixing, stats), tests `test_output_channel.py` and `test_chirp.py` | `pytest` and `ruff` pass; all numbers in section 7 for those two files are met |
| M2 | `backends/base.py`, `fake.py`, `wasapi.py`; `docs/NOTES.md` started | Fake backend tests pass. WASAPI file imports on Linux without error. Mark `needs-hw-test` (not `done`) because the real backend cannot be verified here |
| M3 | `engine.py`, `cli.py` (`devices`, `run`), `config.py`, `logging_setup.py`, `test_engine.py`, `test_cli.py`, `test_config.py` | All tests pass; `python -m partysync devices` works against the fake backend with a `--fake` flag. Mark `needs-hw-test` |
| M4 | `calibration.py`, CLI `calibrate`, `test_calibration.py` | Accuracy and failure-case tests pass. Mark `needs-hw-test` |
| M5 | GUI (5.8) | GUI starts on Windows with the real backend and with `--fake` on any OS (use a virtual display in CI only if easy; otherwise a smoke test that builds the widgets with a headless Tk guard). Mark `needs-hw-test` |
| M6 | `scripts/build_exe.ps1`, `HARDWARE_TEST.md`, `NOTES.md` finished, README usage | Docs are complete and consistent with the code. Mark `done` |
| M7 | Not yours. The user runs the hardware checks | |
| M8 | Optional stretch (only if asked): N speakers, auto-reconnect, tap-to-nudge, per-pair presets | |

## 11. Rules for commits, status and honesty

- Branch per milestone, e.g. `m1-core-dsp`. Commit format `type(scope): summary`. Hooks enforce it.
- Before you finish: `python -m pytest -q`, `python -m ruff check .`, `python scripts/status.py check`.
- Update status only through `scripts/status.py`. Use `needs-hw-test` for anything that depends on real Windows audio or real speakers.
- Never write "verified on hardware" anywhere. Only the user's `status.py hw ... pass` records do that.
- When you must guess, write the guess in `docs/NOTES.md`, not as a comment that sounds like a fact.
- Keep functions small and typed. Public functions get one-line docstrings stating units (ms, frames, seconds) because unit mix-ups are the most likely bug in this project.
- Do not add dependencies beyond section 2 without recording why in `docs/NOTES.md`.

## 12. Final report format (what you tell the user when a milestone is done)

1. Milestone id and the status you set.
2. The commands you ran and their result (test counts, ruff).
3. Anything that deviates from this spec.
4. Anything that needs real hardware to confirm, listed by the H-numbers it affects.
5. The next milestone.
