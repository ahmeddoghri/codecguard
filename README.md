# codecguard

[![tests](https://github.com/ahmeddoghri/codecguard/actions/workflows/tests.yml/badge.svg)](https://github.com/ahmeddoghri/codecguard/actions/workflows/tests.yml) [![case study](https://img.shields.io/badge/case%20study-adoghri.com-e0703e)](https://adoghri.com/project-63.html)

**A CI quality gate for audio codec changes.**

Generate a reference master, execute a real FFmpeg encode/decode, and fail a release when the codec damages spectrum, transients, stereo width, or signal-to-noise ratio.

![codecguard cover](demo/cover.png)

![codecguard workbench](demo/dashboard.png)

## What ships

- Deterministic stereo master with tones, chirps, wide content, and hard transients
- Real AAC/MP3/Opus round trips through FFmpeg
- Multi-resolution spectral convergence, SNR, transient-retention, and stereo-width gates
- CLI, JSON API, interactive regression console, Docker, tests

## Run it end to end

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
codecguard benchmark artifacts --codec aac --bitrate 192k
codecguard serve
```

## Demo result

The release candidate preserves the test master and passes all four gates. A low-pass, stereo-collapsed regression is rejected with the failed dimensions shown independently. The integration test also encodes and decodes a real AAC artifact before measuring it.

## Research basis

Codec evaluation needs complementary time, frequency, spatial, and perceptual evidence. This focused implementation makes the deterministic signal-level layer reproducible in CI; listening tests remain part of release sign-off.

## Update: fixed a crash on clips shorter than the FFT window

The multi-resolution spectral-convergence loop floored `frame_count` to a
minimum of 1 even when the clip was shorter than the current FFT window
size (512/2048/8192 samples). For any clip under 8192 samples (~170ms at
48kHz -- an ordinary length for a short SFX or dialogue snippet), the
fancy-indexed frame windows reached past the signal's actual length and
raised an uncaught `IndexError`.

This directly contradicted the intent of the repo's own
`test_short_inputs_remain_measurable` test, which only happened to pass
because its fixture (10,000 samples) was longer than the largest window
(8,192) by luck -- anything shorter crashed.

Verified directly: `measure()` on identical 500-, 2,000-, 5,000-, and
8,191-sample clips all crashed before the fix. Fixed by only using FFT
window sizes that fit within the clip, falling back to a single
whole-clip window for very short audio. `tests/test_very_short_clips.py`
covers the crash range plus a demo-output regression check; the published
demo result (release candidate passes, regression fails on all four
gates) is unaffected.

## Test

```bash
python -m unittest discover -s tests -v
```

MIT licensed.
