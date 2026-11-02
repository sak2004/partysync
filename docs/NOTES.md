# Notes

## Decisions

- M2 uses a deterministic virtual clock in FakeWorld. Tests advance it explicitly with run(seconds), so no audio test depends on wall-clock scheduling.
- Fake microphone audio is block-based and models output latency, optional acoustic delay, additive noise, and short echoes. This supports future engine and calibration tests without sound hardware.

## Deviations

- The web MVP uses Flask as the primary GUI and Streamlit as an optional alternative, replacing the original Tkinter M5 plan at the user's request.
- The existing src package layout is retained instead of creating a second root-level partysync package.

## Packaging

- The `scripts/build_exe.ps1` script was written in a CI sandbox and the resulting
  `dist\PartySync.exe` has **not** been run on a Windows machine with real audio hardware.
  Verify the exe launches and the web dashboard opens on first real Windows run.
- PyAudioWPatch binary collection via `--collect-all pyaudiowpatch` is assumed to include
  the necessary DLLs and PortAudio binaries. Confirm that no "DLL not found" error appears
  when the exe first runs.
- The engine keep-alive loopback stream (opened on the source endpoint to prevent WASAPI
  from stopping loopback delivery) needs real WASAPI verification. See H3 and H4 in
  `docs/HARDWARE_TEST.md`.
- Flask opens on `0.0.0.0:5000`. The first run on Windows may trigger a **Windows Firewall
  prompt** asking to allow network access. Allow access for the local network (or private
  networks only) for the dashboard to be reachable.

## Assumptions to verify on Windows

- PyAudioWPatch loopback enumeration and device indices correspond to the WASAPI endpoint indices accepted by open.
- Float32 callback streams are accepted for source, output, and microphone endpoints at each endpoint advertised mix rate.
- An endpoint which rejects two channels can be reopened using its native channel count; the current adapter does not yet perform that fallback.
- Some endpoints may need a 48 kHz or 44.1 kHz retry after an invalid-sample-rate failure.
- Bluetooth device removal can surface as exceptions other than OSError.
