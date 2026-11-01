# Notes

## Decisions

- M2 uses a deterministic virtual clock in FakeWorld. Tests advance it explicitly with run(seconds), so no audio test depends on wall-clock scheduling.
- Fake microphone audio is block-based and models output latency, optional acoustic delay, additive noise, and short echoes. This supports future engine and calibration tests without sound hardware.

## Deviations

- None so far.

## Assumptions to verify on Windows

- PyAudioWPatch loopback enumeration and device indices correspond to the WASAPI endpoint indices accepted by open.
- Float32 callback streams are accepted for source, output, and microphone endpoints at each endpoint advertised mix rate.
- An endpoint which rejects two channels can be reopened using its native channel count; the current adapter does not yet perform that fallback.
- Some endpoints may need a 48 kHz or 44.1 kHz retry after an invalid-sample-rate failure.
- Bluetooth device removal can surface as exceptions other than OSError.
