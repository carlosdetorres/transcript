# 🎙️ Transcriptor

Aplicación macOS para transcribir audios usando **OpenAI Whisper**.

## ✨ Características

- **Formatos soportados:** WAV, MP3, OGG, M4A, OPUS, WEBM, FLAC
- **Barra de progreso** visual con estimación de tiempo
- **Notificaciones nativas** de macOS
- **Auto-organización:** Los audios procesados se mueven a `historical/`
- **Detección automática de idioma** por archivo
- **App nativa** para el Dock de macOS

## 🚀 Instalación

```bash
# Clonar el repo
git clone https://github.com/carlosdetorres/transcript.git
cd transcript

# Crear entorno virtual
python3 -m venv venv

# Instalar dependencias
./venv/bin/pip install -r requirements.txt

# (Opcional) Instalar ffprobe para estimación precisa de duración
brew install ffmpeg
```

## 📱 Uso

### Opción 1: Doble clic en `Transcriptor.app`
1. Arrastra `Transcriptor.app` al Dock
2. Doble clic → se abre carpeta `audio/`
3. Mete tus archivos
4. Elige **Español** o **Inglés** en el diálogo
5. Al terminar se abre `transcriptions/`

### Opción 2: Terminal
```bash
# Meter audios en la carpeta audio/
./venv/bin/python transcribe.py

# Forzar idioma si lo sabes de antemano
./venv/bin/python transcribe.py --language es
./venv/bin/python transcribe.py --language en
```

La app te pide elegir idioma antes de transcribir. Por terminal puedes forzarlo con `--language es`, `--language en`, o usar `--language auto` para detección automática por archivo.

## 📁 Estructura

```
transcript/
├── Transcriptor.app   ← App para el Dock
├── audio/             ← Mete audios aquí
├── historical/        ← Audios ya procesados
├── transcriptions/    ← Transcripciones .txt
├── transcribe.py      ← Script principal
└── requirements.txt
```

## ⚙️ Requisitos

- Python 3.8+
- macOS 10.14+
- ~1.5GB para el modelo Whisper medium
