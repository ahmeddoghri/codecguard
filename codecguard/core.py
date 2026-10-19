from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path


THRESHOLDS = {"snr_db": 18.0, "spectral_convergence": 0.18, "transient_retention": 0.82, "stereo_width_error": 0.12}


def _np():
    import numpy as np
    return np


def fixture(sample_rate: int = 48000, duration: float = 3.0):
    np = _np()
    t = np.arange(round(sample_rate * duration), dtype=np.float64) / sample_rate
    left = .34 * np.sin(2 * np.pi * 220 * t) + .19 * np.sin(2 * np.pi * 3100 * t)
    right = .32 * np.sin(2 * np.pi * 330 * t + .4) + .17 * np.sin(2 * np.pi * 5700 * t)
    chirp = .12 * np.sin(2 * np.pi * (180 * t + 1700 * t * t))
    left += chirp
    right += chirp[::-1]
    for at in (.45, 1.35, 2.25):
        start = round(at * sample_rate)
        decay = np.exp(-np.arange(1200) / 145)
        left[start:start + 1200] += .56 * decay
        right[start:start + 1200] -= .43 * decay
    return np.clip(np.column_stack((left, right)), -.98, .98).astype(np.float32)


def _write(path: str | Path, audio, sample_rate: int = 48000) -> Path:
    np = _np()
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2); output.setsampwidth(2); output.setframerate(sample_rate); output.writeframes(pcm.tobytes())
    return Path(path)


def _read(path: str | Path):
    np = _np()
    with wave.open(str(path), "rb") as source:
        rate = source.getframerate(); channels = source.getnchannels(); raw = source.readframes(source.getnframes())
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, channels) / 32768
    if channels == 1: audio = np.repeat(audio, 2, axis=1)
    return audio, rate


def measure(reference, candidate, thresholds: dict | None = None) -> dict:
    np = _np(); thresholds = thresholds or THRESHOLDS
    # Raw elementary streams can expose encoder priming. Align on the signal
    # before scoring so container delay is not mistaken for audible damage.
    probe = min(8000, len(reference), len(candidate))
    search = min(len(candidate), probe + 4096)
    if probe > 256 and search >= probe:
        ref_mono = reference[:probe].mean(axis=1)
        cand_mono = candidate[:search].mean(axis=1)
        lag = int(np.argmax(np.correlate(cand_mono, ref_mono, mode="valid")))
        candidate = candidate[lag:]
    else:
        lag = 0
    count = min(len(reference), len(candidate)); reference = reference[:count]; candidate = candidate[:count]
    error = reference - candidate
    snr = 10 * np.log10((np.mean(reference ** 2) + 1e-12) / (np.mean(error ** 2) + 1e-12))
    convergences = []
    # frame_count was floored to a minimum of 1 even when `count < size`,
    # so a clip shorter than the FFT window (e.g. under 8192 samples, ~170ms
    # at 48kHz -- an ordinary length for short SFX or dialogue clips) made
    # `indices` reach past the signal's actual length, raising an uncaught
    # IndexError on the fancy-indexed reference[indices]/candidate[indices].
    sizes = [size for size in (512, 2048, 8192) if size <= count] or [count]
    for size in sizes:
        hop = max(1, size // 2); frame_count = max(1, (count - size) // hop + 1)
        indices = np.arange(size)[None, :] + hop * np.arange(frame_count)[:, None]
        window = np.hanning(size)[None, :, None]
        ref_spec = np.abs(np.fft.rfft(reference[indices] * window, axis=1))
        cand_spec = np.abs(np.fft.rfft(candidate[indices] * window, axis=1))
        convergences.append(float(np.linalg.norm(ref_spec - cand_spec) / (np.linalg.norm(ref_spec) + 1e-12)))
    ref_diff = np.max(np.abs(np.diff(reference, axis=0)), axis=1)
    cand_diff = np.max(np.abs(np.diff(candidate, axis=0)), axis=1)
    peaks = np.argpartition(ref_diff, -12)[-12:]
    transient = float(np.mean([np.max(cand_diff[max(0, p-3):p+4]) / (ref_diff[p] + 1e-9) for p in peaks]))
    def width(signal): return float(np.sqrt(np.mean(((signal[:, 0] - signal[:, 1]) * .5) ** 2)))
    width_error = abs(width(candidate) - width(reference)) / (width(reference) + 1e-12)
    metrics = {"snr_db": round(float(snr), 3), "spectral_convergence": round(max(convergences), 5), "transient_retention": round(transient, 4), "stereo_width_error": round(width_error, 5)}
    checks = {"snr": metrics["snr_db"] >= thresholds["snr_db"], "spectrum": metrics["spectral_convergence"] <= thresholds["spectral_convergence"], "transients": metrics["transient_retention"] >= thresholds["transient_retention"], "stereo": metrics["stereo_width_error"] <= thresholds["stereo_width_error"]}
    return {"passed": all(checks.values()), "alignment_samples": lag, "metrics": metrics, "checks": checks, "thresholds": thresholds, "scope": "Signal-level codec regression; perceptual listening tests remain necessary for release sign-off."}


def demo() -> dict:
    np = _np(); reference = fixture(); rng = np.random.default_rng(7)
    good = np.clip(reference + rng.normal(0, .006, reference.shape), -1, 1)
    kernel = np.ones(19) / 19
    bad = np.column_stack([np.convolve(reference[:, channel], kernel, mode="same") for channel in range(2)])
    bad[:, 1] = bad[:, 0] * .97
    return {"release_candidate": measure(reference, good), "regression": measure(reference, bad)}


# An encoder name is not a container name. Deriving the output extension
# from the codec worked for "aac" by luck and was special-cased for
# libmp3lame; everything else, libopus and libvorbis included, produced a
# filename ffmpeg could not choose a muxer for and failed the encode.
CONTAINER_FOR_CODEC = {
    "aac": "m4a", "libfdk_aac": "m4a", "alac": "m4a",
    "libmp3lame": "mp3", "mp3": "mp3",
    "libopus": "opus", "opus": "opus",
    "libvorbis": "ogg", "vorbis": "ogg",
    "flac": "flac",
    "ac3": "ac3", "eac3": "eac3",
    "pcm_s16le": "wav", "pcm_s24le": "wav",
}


def container_for(codec: str) -> str:
    """Container extension ffmpeg can mux this codec into."""
    try:
        return CONTAINER_FOR_CODEC[codec]
    except KeyError:
        raise ValueError(
            f"unknown codec {codec!r}: add it to CONTAINER_FOR_CODEC with the "
            "container extension ffmpeg should mux it into"
        ) from None


def benchmark(directory: str | Path, codec: str = "aac", bitrate: str = "192k") -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg: raise RuntimeError("ffmpeg is required")
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    reference_path, encoded_path, decoded_path = directory / "reference.wav", directory / f"candidate.{container_for(codec)}", directory / "decoded.wav"
    _write(reference_path, fixture())
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(reference_path), "-c:a", codec, "-b:a", bitrate, str(encoded_path)], check=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(encoded_path), "-ac", "2", "-ar", "48000", str(decoded_path)], check=True)
    reference, _ = _read(reference_path); candidate, _ = _read(decoded_path)
    result = measure(reference, candidate); result["artifacts"] = {"reference": str(reference_path), "encoded": str(encoded_path), "decoded": str(decoded_path)}
    result["codec"] = codec; result["bitrate"] = bitrate
    return result
