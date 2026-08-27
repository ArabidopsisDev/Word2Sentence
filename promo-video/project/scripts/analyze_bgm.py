from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "project" / "config.json"
FFMPEG_FALLBACK = ROOT / "tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe"


def resolve(path: str) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else ROOT / value).resolve()


def load_audio(ffmpeg: Path, source: Path, sample_rate: int) -> np.ndarray:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:a:0", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ]
    completed = subprocess.run(command, capture_output=True, check=True)
    return np.frombuffer(completed.stdout, dtype="<f4").copy()


def frame_rms(audio: np.ndarray, sample_rate: int, seconds: float = 0.5) -> np.ndarray:
    size = max(1, round(sample_rate * seconds))
    trimmed = audio[: len(audio) // size * size]
    return np.sqrt(np.mean(trimmed.reshape(-1, size) ** 2, axis=1) + 1e-12)


def onset_envelope(audio: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
    frame, hop = 2048, 512
    frames = np.lib.stride_tricks.sliding_window_view(audio, frame)[::hop]
    window = np.hanning(frame).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1)).astype(np.float32)
    spectrum = np.log1p(12.0 * spectrum)
    flux = np.maximum(spectrum[1:] - spectrum[:-1], 0.0).mean(axis=1)
    flux = np.concatenate(([0.0], flux))
    kernel = np.ones(5, dtype=np.float32) / 5.0
    flux = np.convolve(flux, kernel, mode="same")
    low = np.percentile(flux, 20)
    high = np.percentile(flux, 99)
    flux = np.clip((flux - low) / max(1e-9, high - low), 0.0, 1.0)
    return flux.astype(np.float32), hop


def tempo_candidates(envelope: np.ndarray, sample_rate: int, hop: int) -> list[dict]:
    centered = envelope - np.mean(envelope)
    candidates = []
    for bpm in np.arange(60.0, 181.0, 0.1):
        lag = max(1, round(60.0 * sample_rate / (hop * bpm)))
        score = float(np.dot(centered[:-lag], centered[lag:]) / max(1, len(centered) - lag))
        candidates.append((score, float(bpm), lag))
    selected: list[dict] = []
    for score, bpm, lag in sorted(candidates, reverse=True):
        if any(abs(bpm - item["bpm"]) < 1.5 for item in selected):
            continue
        phase_scores = [float(envelope[phase::lag].sum()) for phase in range(lag)]
        phase = int(np.argmax(phase_scores))
        selected.append({
            "bpm": round(bpm, 2),
            "autocorrelation": score,
            "beat_seconds": round(60.0 / bpm, 6),
            "phase_seconds": round((phase * hop) / sample_rate, 6),
        })
        if len(selected) == 8:
            break
    return selected


def local_minima(values: np.ndarray, interval_seconds: float, start: float, end: float) -> list[dict]:
    radius = max(1, round(2.0 / interval_seconds))
    minima = []
    for index in range(radius, len(values) - radius):
        time = index * interval_seconds
        if not start <= time <= end:
            continue
        window = values[index - radius:index + radius + 1]
        if values[index] <= np.min(window):
            minima.append({"time": round(time, 3), "rms": float(values[index])})
    return sorted(minima, key=lambda item: item["rms"])[:16]


def draw_waveform(rms: np.ndarray, interval: float, duration: float, points: list[float], output: Path) -> None:
    width, height = 1800, 640
    image = Image.new("RGB", (width, height), "#F5F4F0")
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 90, 1740, 90, 540
    draw.rectangle((left, top, right, bottom), fill="#FFFDF9", outline="#D9D8D2", width=2)
    maximum = max(1e-9, float(np.max(rms)))
    for index, value in enumerate(rms):
        x = left + (index * interval / duration) * (right - left)
        bar = (float(value) / maximum) * (bottom - top - 30)
        draw.line((x, bottom, x, bottom - bar), fill="#2F6048", width=2)
    for point in points:
        x = left + point / duration * (right - left)
        draw.line((x, top, x, bottom), fill="#B83C37", width=3)
    font_path = "C:/Windows/Fonts/CascadiaMono.ttf"
    font = ImageFont.truetype(font_path, 22)
    draw.text((left, 35), "BGM RMS timeline and candidate cadence points", font=font, fill="#242522")
    for second in range(0, math.ceil(duration) + 1, 30):
        x = left + second / duration * (right - left)
        draw.text((x, bottom + 18), f"{second}s", font=font, fill="#686A64", anchor="ma")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = resolve(str(config["audio"]["source"]))
    ffmpeg_value = str(config.get("tools", {}).get("ffmpeg", "") or "")
    ffmpeg = resolve(ffmpeg_value) if ffmpeg_value else FFMPEG_FALLBACK
    sample_rate = 22050
    audio = load_audio(ffmpeg, source, sample_rate)
    duration = len(audio) / sample_rate
    rms_interval = 0.5
    rms = frame_rms(audio, sample_rate, rms_interval)
    envelope, hop = onset_envelope(audio, sample_rate)
    candidates = tempo_candidates(envelope, sample_rate, hop)
    minima = local_minima(rms, rms_interval, 80.0, min(125.0, duration - 5.0))
    report = {
        "source": str(source),
        "duration": round(duration, 6),
        "sample_rate_analysis": sample_rate,
        "tempo_candidates": candidates,
        "low_energy_cadence_candidates_80_125": minima,
        "rms_half_second": [round(float(value), 7) for value in rms],
    }
    report_path = ROOT / "project" / "docs" / "BGM_ANALYSIS.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    draw_waveform(rms, rms_interval, duration, [item["time"] for item in minima[:8]], ROOT / "renders" / "bgm-waveform.png")
    print(json.dumps({"duration": report["duration"], "tempo_candidates": candidates, "cadence_candidates": minima[:8]}, indent=2))


if __name__ == "__main__":
    main()

