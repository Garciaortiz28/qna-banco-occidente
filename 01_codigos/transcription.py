"""
transcription.py — Servicio de transcripción de audio con Groq Whisper
"""
import os
import tempfile
import requests
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
WHISPER_MODEL      = "whisper-large-v3-turbo"


def transcribe_whatsapp_audio(media_url: str) -> str:
    """
    Descarga audio de Twilio y transcribe con Groq Whisper.
    Retorna el texto transcrito en español.
    """
    print(f"[voice] Descargando audio de Twilio...")

    response = requests.get(
        media_url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(f"Error descargando audio: {response.status_code}")

    print(f"[voice] Audio descargado: {len(response.content)} bytes")

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(response.content)
        temp_path = f.name

    try:
        print(f"[voice] Transcribiendo con Groq Whisper ({WHISPER_MODEL})...")
        client = Groq(api_key=GROQ_API_KEY)

        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(temp_path), audio_file, "audio/ogg"),
                model=WHISPER_MODEL,
                language="es",
                response_format="text",
                prompt="Esto es una consulta bancaria al Banco de Occidente Colombia.",
            )

        texto = (
            transcription.strip()
            if isinstance(transcription, str)
            else transcription.text.strip()
        )
        print(f"[voice] Transcripción: '{texto[:100]}'")
        return texto

    finally:
        os.unlink(temp_path)
