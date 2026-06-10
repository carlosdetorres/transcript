#!/usr/bin/env python3
"""
🎙️ Transcriptor de Audio - Carlos Edition
Transcribes audio with MLX Whisper + speaker diarization (Senko).
"""

import argparse
import shutil
import subprocess
import sys
import threading
import time
import warnings
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
AUDIO_DIR = SCRIPT_DIR / "audio"
OUTPUT_DIR = SCRIPT_DIR / "transcriptions"
HISTORICAL_DIR = SCRIPT_DIR / "historical"

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".opus"}

DEFAULT_MODEL = "whisper-diarize"
DEFAULT_LANGUAGE = "es"

MODELS = {
    "whisper-diarize": {
        "label": "Whisper Diarize",
        "description": "MLX + diarización (SPEAKER_01, SPEAKER_02…)",
        "suffix": "whisper-diarize",
        "ratio": 0.15,
    },
    "whisper-medium": {
        "label": "Whisper Medium",
        "description": "texto plano, sin hablantes",
        "suffix": "whisper-medium",
        "ratio": 0.35,
    },
}

LANGUAGE_NAMES = {
    "es": "Español",
    "en": "Inglés",
}


def notify(title: str, message: str, sound: bool = True):
    sound_cmd = 'sound name "Glass"' if sound else ""
    script = f'display notification "{message}" with title "{title}" {sound_cmd}'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def format_time(seconds: int) -> str:
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02d}:{secs:02d}"


def get_audio_duration(file_path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        return size_mb * 6


def show_progress_bar(stop_event: threading.Event, estimated_seconds: float):
    bar_width = 30
    idx = 0

    while not stop_event.is_set():
        elapsed = idx
        if estimated_seconds > 0:
            progress = min(elapsed / estimated_seconds, 0.99)
            filled = int(bar_width * progress)
            bar = "█" * filled + "░" * (bar_width - filled)
            percent = int(progress * 100)
            sys.stdout.write(
                f"\r   [{bar}] {percent:2d}% • {format_time(elapsed)} / ~{format_time(estimated_seconds)}"
            )
        else:
            chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            sys.stdout.write(f"\r   {chars[idx % len(chars)]} Procesando... {format_time(elapsed)}")

        sys.stdout.flush()
        time.sleep(1)
        idx += 1

    bar = "█" * bar_width
    sys.stdout.write(f"\r   [{bar}] ✅ Completado en {format_time(idx)}      \n")
    sys.stdout.flush()


def output_filename(stem: str, model_key: str) -> str:
    return f"{stem}_{MODELS[model_key]['suffix']}.txt"


def load_whisper_model():
    import whisper

    return whisper.load_model("medium")


def transcribe_whisper_medium(model, audio_file: Path, language: str | None) -> dict:
    transcribe_kwargs = {}
    if language:
        transcribe_kwargs["language"] = language
    return model.transcribe(str(audio_file), **transcribe_kwargs)


def load_pipeline(model_key: str):
    if model_key == "whisper-medium":
        print("\n🧠 Cargando Whisper (medium)...")
        model = load_whisper_model()
        print("✅ Modelo listo\n")
        return model

    print("\n🧠 Cargando pipeline (primera vez puede descargar ~1.5 GB)...")
    from diarize_pipeline import warmup_pipeline

    warmup_pipeline()
    print()
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Transcribe audios en español con diarización.")
    parser.add_argument(
        "--language",
        choices=["auto", "es", "en"],
        default=DEFAULT_LANGUAGE,
        help="Idioma a forzar. Por defecto: es.",
    )
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default=DEFAULT_MODEL,
        help=f"Modelo de transcripción (por defecto: {DEFAULT_MODEL}).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    model_config = MODELS[args.model]

    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

    for directory in [AUDIO_DIR, OUTPUT_DIR, HISTORICAL_DIR]:
        directory.mkdir(exist_ok=True)

    audio_files = sorted(
        file_path
        for file_path in AUDIO_DIR.iterdir()
        if file_path.suffix.lower() in AUDIO_EXTENSIONS
    )

    if not audio_files:
        print("━" * 50)
        print("⚠️  No hay archivos de audio en la carpeta 'audio/'")
        print(f"   Formatos: {', '.join(sorted(AUDIO_EXTENSIONS))}")
        print("━" * 50)
        notify("Transcriptor", "No hay archivos de audio para procesar")
        return

    print("━" * 50)
    print("🎙️  TRANSCRIPTOR DE AUDIO")
    print("━" * 50)
    print(f"\n🧠 Modelo: {model_config['label']} — {model_config['description']}")
    if args.language == "auto":
        print("🌐 Idioma: detección automática")
    else:
        language_label = LANGUAGE_NAMES.get(args.language, args.language)
        print(f"🌐 Idioma: {language_label}")
    print(f"\n📁 {len(audio_files)} archivo(s) encontrados:\n")

    for audio_file in audio_files:
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        duration = get_audio_duration(audio_file)
        print(f"   • {audio_file.name} ({size_mb:.1f} MB, ~{format_time(duration)})")

    whisper_model = load_pipeline(args.model)

    notify("Transcriptor", f"Iniciando transcripción de {len(audio_files)} archivo(s)")

    total_time = 0
    results = []
    forced_language = None if args.language == "auto" else args.language

    for index, audio_file in enumerate(audio_files, 1):
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📝 [{index}/{len(audio_files)}] {audio_file.name}")

        audio_duration = get_audio_duration(audio_file)
        estimated_process_time = audio_duration * model_config["ratio"]

        stop_event = threading.Event()
        progress_thread = threading.Thread(
            target=show_progress_bar,
            args=(stop_event, estimated_process_time),
        )
        progress_thread.daemon = True

        start_time = time.time()
        progress_thread.start()

        if args.model == "whisper-medium":
            result = transcribe_whisper_medium(whisper_model, audio_file, forced_language)
        else:
            from diarize_pipeline import transcribe_with_diarization

            result = transcribe_with_diarization(
                audio_file,
                language=forced_language or DEFAULT_LANGUAGE,
            )

        stop_event.set()
        progress_thread.join()

        duration = int(time.time() - start_time)
        total_time += duration

        output_file = OUTPUT_DIR / output_filename(audio_file.stem, args.model)
        text = result["text"].strip()
        output_file.write_text(text)

        word_count = len(text.split())
        print(f"   💾 {output_file.name} ({word_count} palabras)")
        if args.language == "auto":
            detected_language = result.get("language")
            if detected_language:
                language_label = LANGUAGE_NAMES.get(detected_language, detected_language.upper())
                print(f"   🌐 Idioma detectado: {language_label}")
        else:
            language_label = LANGUAGE_NAMES.get(args.language, args.language.upper())
            print(f"   🌐 Idioma: {language_label}")

        historical_file = HISTORICAL_DIR / audio_file.name
        if historical_file.exists():
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            historical_file = HISTORICAL_DIR / f"{audio_file.stem}_{timestamp}{audio_file.suffix}"

        shutil.move(str(audio_file), str(historical_file))
        print(f"   📦 → historical/{historical_file.name}")

        results.append({"name": audio_file.stem, "words": word_count, "time": duration})

    print("\n" + "━" * 50)
    print("🎉 RESUMEN")
    print("━" * 50)

    total_words = sum(result["words"] for result in results)
    print(f"\n   📄 {len(results)} archivo(s) transcritos")
    print(f"   📝 {total_words:,} palabras totales")
    print(f"   ⏱️  Tiempo total: {format_time(total_time)}")
    print(f"   🧠 Modelo: {model_config['label']}")
    print("\n   📁 Transcripciones: transcriptions/")
    print("   📦 Audios movidos:  historical/")
    print("\n" + "━" * 50)

    notify(
        "✅ Transcripción Completa",
        f"{len(results)} archivo(s) • {total_words:,} palabras • {format_time(total_time)}",
    )

    subprocess.run(["open", str(OUTPUT_DIR)])


if __name__ == "__main__":
    main()
