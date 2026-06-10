"""MLX Whisper + Senko diarization pipeline for Apple Silicon."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import mlx_whisper
import senko
from mlx_whisper.load_models import load_model

MLX_WHISPER_REPO = "mlx-community/whisper-medium-mlx"

_diarizer: senko.Diarizer | None = None
_pipeline_ready = False


def get_diarizer() -> senko.Diarizer:
    global _diarizer
    if _diarizer is None:
        _diarizer = senko.Diarizer(
            device="auto",
            vad="auto",
            clustering="auto",
            warmup=True,
            quiet=True,
        )
    return _diarizer


def warmup_pipeline() -> None:
    """Pre-load Whisper MLX weights and Senko before processing any file."""
    global _pipeline_ready
    if _pipeline_ready:
        return

    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

    print("   • Whisper MLX (medium)...", flush=True)
    load_model(MLX_WHISPER_REPO)

    print("   • Diarización Senko (CoreML)...", flush=True)
    get_diarizer()

    _pipeline_ready = True
    print("   ✅ Pipeline cargado", flush=True)


def convert_to_wav_16k_mono(audio_path: Path) -> Path:
    """Convert any supported audio to 16 kHz mono 16-bit WAV for Senko."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    wav_path = Path(tmp.name)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


def assign_speaker(seg_start: float, seg_end: float, diar_segments: list[dict]) -> str:
    """Pick the speaker with the largest time overlap for a transcript segment."""
    best_speaker = None
    best_overlap = 0.0

    for segment in diar_segments:
        overlap = min(segment["end"], seg_end) - max(segment["start"], seg_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = segment["speaker"]

    if best_speaker is not None:
        return best_speaker

    if not diar_segments:
        return "SPEAKER_00"

    midpoint = (seg_start + seg_end) / 2
    nearest = min(
        diar_segments,
        key=lambda segment: abs((segment["start"] + segment["end"]) / 2 - midpoint),
    )
    return nearest["speaker"]


def format_diarized_text(segments: list[dict]) -> str:
    """Merge consecutive segments from the same speaker into labeled blocks."""
    lines: list[str] = []
    current_speaker = None
    current_parts: list[str] = []

    for segment in segments:
        speaker = segment.get("speaker", "SPEAKER_00")
        text = segment.get("text", "").strip()
        if not text:
            continue

        if speaker == current_speaker:
            current_parts.append(text)
        else:
            if current_speaker and current_parts:
                lines.append(f"{current_speaker}: {' '.join(current_parts)}")
            current_speaker = speaker
            current_parts = [text]

    if current_speaker and current_parts:
        lines.append(f"{current_speaker}: {' '.join(current_parts)}")

    return "\n\n".join(lines)


def transcribe_with_diarization(audio_path: Path, language: str = "es") -> dict:
    """
    Transcribe audio with mlx-whisper and assign speakers via Senko (CoreML).

    Returns a dict compatible with the whisper result shape used by transcribe.py.
    """
    whisper_result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=MLX_WHISPER_REPO,
        verbose=None,
        language=language,
    )
    segments = whisper_result.get("segments") or []

    wav_path = convert_to_wav_16k_mono(audio_path)
    try:
        diarizer = get_diarizer()
        diarization = diarizer.diarize(str(wav_path), generate_colors=False)
    finally:
        wav_path.unlink(missing_ok=True)

    diar_segments = []
    if diarization:
        diar_segments = diarization.get("merged_segments") or []

    labeled_segments = []
    for segment in segments:
        labeled = dict(segment)
        labeled["speaker"] = assign_speaker(
            float(segment.get("start", 0.0)),
            float(segment.get("end", segment.get("start", 0.0))),
            diar_segments,
        )
        labeled_segments.append(labeled)

    text = format_diarized_text(labeled_segments)
    if not text:
        text = whisper_result.get("text", "").strip()

    return {
        "text": text,
        "language": language,
        "segments": labeled_segments,
    }
