# Hardware Test Guide

Run these checks on the Windows laptop with the **JBL Flip 7** and **JBL Charge 4** connected.
Record each result with `python scripts/status.py hw <id> pass|fail --note "..."`.

> **Before you start:** both speakers should be paired in Windows Bluetooth settings, the
> virtual audio cable installed (e.g. VB-Audio CABLE), and Python dependencies installed
> (`pip install -r requirements.txt`). Open the web dashboard with `python app_flask.py`
> and navigate to `http://localhost:5000` in a browser.

---

## H1 — Both speakers show up as Stereo WASAPI outputs

**Steps:**
1. Pair both speakers via Windows **Settings → Bluetooth & devices**.
2. Open a PowerShell terminal and run:
   ```
   python -m partysync devices --fake
   ```
   This shows the expected output format. Then run:
   ```
   python -m partysync devices
   ```
3. Confirm that **JBL Flip 7** and **JBL Charge 4** both appear as `output` devices.
4. Check that neither entry has a `warning` field containing "Hands-Free". If only a
   Hands-Free entry appears for a speaker, right-click that speaker in **Windows Sound
   settings → Playback** and enable the **Stereo** stream (A2DP profile).
5. Note the device index numbers for use in later tests.

**Pass:** Both devices are listed as `output` with no `warning` field (or warning absent).

**Fail / diagnostics:** Open the web dashboard at `http://localhost:5000`, press **F12** in
the browser and check the Console tab. Alternatively, add `--debug` to the Flask run command:
`python app_flask.py --debug`.

**Record:**
```
python scripts/status.py hw H1 pass --note "Flip 7 idx=N, Charge 4 idx=M"
```

---

## H2 — Source capture works and the level meter moves

**Steps:**
1. Install and configure **VB-Audio Virtual Cable** (or similar). Set **CABLE Input** as
   the Windows default playback device in **Settings → Sound → Output**.
2. Start the app: `python app_flask.py`. Open `http://localhost:5000`.
3. In the **Source** dropdown, select the CABLE loopback entry (it should be labelled
   something like "CABLE Output" and marked as a loopback source).
4. In **Speaker A** and **Speaker B** dropdowns, select the Stereo entries for JBL Flip 7
   and JBL Charge 4 respectively.
5. Click **Start** in the dashboard.
6. Play audio on the laptop (Spotify, YouTube, etc. — anything that outputs to the default
   device).
7. Watch the level meter on the dashboard; it should animate in response to the music.
8. As a simulated sanity check (no real speakers needed), you may first run with
   `python app_flask.py` and select a `[Fake]` source to confirm the UI path works.

**Pass:** The level meter moves while audio is playing.

**Fail / diagnostics:** If the meter stays at zero, check that the source app is outputting
to the correct device. Press **F12** in the browser and inspect the Console. Run
`python -m partysync devices` and confirm the CABLE loopback source is listed.

**Record:**
```
python scripts/status.py hw H2 pass --note "Level meter moves, source CABLE idx=N"
```

---

## H3 — Audio plays on both speakers simultaneously with no feedback loop

**Steps:**
1. With both speakers selected (H2 complete), click **Start**.
2. Play audio. Confirm you hear sound from **both** the Flip 7 and Charge 4.
3. Confirm there is no howl or echo feedback. The source must be the virtual cable, **not**
   one of the speaker endpoints.
4. If you hear a feedback loop, click **Stop** immediately, then go to the Source dropdown
   and make sure it is set to the CABLE loopback — never to either speaker.

**Pass:** Audio audible from both speakers, no howl, no error message in the dashboard.

**Fail / diagnostics:** The dashboard status bar will show which channel has an error. Press
**F12 → Console** in the browser for stack traces. Run with `python app_flask.py --debug`
for verbose engine logging.

**Record:**
```
python scripts/status.py hw H3 pass --note "Both speakers playing, no feedback"
```

---

## H4 — 30-minute dropout-free playback

**Steps:**
1. With both speakers playing (H3 confirmed), start a 30-minute playlist or stream.
2. Keep the laptop awake (disable sleep in **Settings → Power**).
3. Monitor the dashboard every few minutes:
   - **Fill ms** should stay above zero for both channels.
   - **Underruns** and **Jumps** counters should stay at zero (or very low).
4. At the end of 30 minutes, note the total underrun and jump counts.

**Pass:** No audible dropout or crackle during 30 minutes; underrun count remains 0 (or
only 1-2 for brief system interruptions).

**Fail / diagnostics:** If dropouts occur, note the time and the dashboard fill/underrun
values. Copy diagnostics: click **Copy diagnostics** in the dashboard (or press F12 and
capture the Console log). Run `python app_flask.py --debug` for more detail.

**Record:**
```
python scripts/status.py hw H4 pass --note "30 min, 0 underruns, 0 jumps"
```

---

## H5 — Calibration result agrees with by-ear tuning within 10 ms

**Steps:**
1. Place the laptop roughly where people will listen, with both speakers at party volume.
2. Make sure the room is quiet (no HVAC hum, no music in the background).
3. In the dashboard, select the **laptop microphone** in the Microphone dropdown.
4. Click **Calibrate**. Confirm the warning dialog ("You will hear loud sweeps for about 20
   seconds…") and click **Continue**.
5. Wait for the result. Note the reported delay (e.g. "Charge 4 is 148.3 ms slower.
   Delaying Flip 7 by 148 ms.").
6. **By-ear check:** Open a metronome app at **120 BPM** (500 ms between beats). Play it
   through both speakers. Listen for a "flam" (double hit) — if you hear one, the alignment
   is off by more than ~10 ms (1/50th of a beat at 120 BPM). Adjust using the delay buttons
   (+1/−1 ms steps) until the click sounds like a single sharp tap from both speakers.
7. Note the final manually-adjusted delay and compare it to the calibrated value.

**Pass:** The calibrated delay differs from the by-ear tuned value by ≤ 10 ms.

**Fail / diagnostics:** If calibration fails (low PMR / no chirps detected), see H6 steps
below. Press **F12 → Console** in the browser for the calibration log. Run
`python app_flask.py --debug` for full calibration state-machine output.

**Record:**
```
python scripts/status.py hw H5 pass --note "Cal: 148 ms, by-ear: 146 ms, diff 2 ms"
```

---

## H6 — Calibration works with the laptop microphone

**Steps:**
1. In Windows **Settings → Privacy & security → Microphone**, confirm that desktop apps
   have microphone access enabled.
2. Open **Settings → Sound → Input**, select the laptop microphone, and click **Device
   properties**. Under the **Enhancements** tab (or **Additional device properties →
   Enhancements**), **disable all enhancements** — especially echo cancellation, noise
   suppression, and beam-forming. These filters can remove the calibration chirp.
3. Run calibration (same steps as H5 steps 1–4).
4. If the calibration still fails with "mic heard nothing", check that:
   - The mic entry selected in the dashboard matches the laptop mic (not a Bluetooth mic).
   - The mic recording is not all zeros: in Windows Sound settings, speak and confirm the
     input level bar moves.
5. If the calibration fails with "too quiet or too noisy", try: moving the laptop closer to
   the speakers, increasing speaker volume, or further quieting the room.

**Pass:** Calibration completes with `ok = True` using the laptop microphone.

**Fail / diagnostics:** The failure reason shown in the dashboard will identify which speaker
was not heard or whether the mic was silent. Press **F12 → Console** in the browser.
Run `python app_flask.py --debug` for the raw PMR values per chirp detection.

**Record:**
```
python scripts/status.py hw H6 pass --note "Laptop mic, enhancements disabled, cal ok"
```

---

## H7 — Moving the delay slider is click-free

**Steps:**
1. With both speakers playing music (H3 confirmed), set a comfortable volume.
2. In the dashboard, slowly move the **delay slider** for Speaker A (or B) across its
   range (0 to 1000 ms). Listen closely for any audible pops, clicks, or glitches.
3. Repeat by using the **+1**, **−1**, **+10**, **−10** ms buttons during playback.
4. Also try a large jump (e.g. move from 0 ms to 500 ms in one slider drag) — this should
   trigger the crossfade path internally; you may hear a brief "swoosh" or pitch shift but
   not a sharp click.

**Pass:** No sharp clicks or pops when moving the delay slider during playback.

**Fail / diagnostics:** Note the slider position at which the click occurred and the fill
and jump stats in the dashboard status bar at that moment. Press **F12 → Console** and note
any error. Run `python app_flask.py --debug` for engine callback tracing.

**Record:**
```
python scripts/status.py hw H7 pass --note "Slider drag 0-1000 ms click-free, large jumps crossfade audible but no pops"
```

---

## H8 — 60-minute sync test with a click track

**Steps:**
1. After calibration (H5 or H6 confirmed), start a **click track** (metronome) at 120 BPM.
   A click track makes timing drift obvious as a gradual "flamming" of the beat.
2. Start playback through both speakers with calibrated delays applied.
3. At the **30-minute mark**, listen carefully for any flamming. If you hear it, check the
   dashboard drift ppm display; note the value.
4. At the **60-minute mark**, do the same check. The speakers should still sound like a
   single source.
5. If drift is visible (flamming), note the drift ppm estimate from the dashboard and the
   total time since calibration.

**Pass:** At 60 minutes the click track sounds like a single tap (no audible flam) from
both speakers.

**Fail / diagnostics:** Record the drift ppm values and timestamps. Use **Copy diagnostics**
in the dashboard (all stats, last calibration result, device rates). Press **F12 → Console**
or run with `--debug` for detailed per-block fill data.

**Record:**
```
python scripts/status.py hw H8 pass --note "60 min click track, no audible flam, drift <50 ppm"
```

---

## H9 — Speaker power-cycle does not crash the app

**Steps:**
1. With both speakers playing (H3 confirmed), turn **one speaker off** using its power
   button (or disconnect Bluetooth manually in Windows settings).
2. Wait 5 seconds. The dashboard should show the disconnected channel as inactive (the
   other speaker keeps playing).
3. Turn the speaker back on and reconnect it in Windows Bluetooth settings.
4. In the dashboard, click **Stop** then **Start** to restart the engine with both speakers
   reconnected. (Auto-reconnect is a stretch goal; M8. For now a manual Stop/Start is
   expected.)
5. Confirm the app has not crashed and audio is restored on both speakers.

**Pass:** App does not crash; after a Stop/Start the disconnected speaker plays again
normally.

**Fail / diagnostics:** If the app crashes, copy the terminal output (or the `--debug` log)
and the browser Console. Check for `OSError` from PyAudioWPatch — the WASAPI backend is
designed to swallow these; if it does not, note the exception. Run
`python app_flask.py --debug` for detailed stream lifecycle logging.

**Record:**
```
python scripts/status.py hw H9 pass --note "Speaker power-cycled, Stop/Start restored playback, no crash"
```
