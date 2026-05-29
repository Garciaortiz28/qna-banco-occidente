"""
tts_service.py — Conversión texto a voz con gTTS + Cloudinary
"""
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
VOICE_RESPONSE        = os.getenv("VOICE_RESPONSE", "false").lower() == "true"


def text_to_audio_url(text: str) -> str | None:
    """
    Convierte texto a MP3 con gTTS y lo sube a Cloudinary.
    Retorna la URL pública del audio o None si falla.
    """
    if not VOICE_RESPONSE:
        return None
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        print("[tts] Cloudinary no configurado — solo respuesta en texto")
        return None

    try:
        from gtts import gTTS
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )

        texto_audio = text[:500] if len(text) > 500 else text

        print(f"[tts] Generando audio ({len(texto_audio)} chars)...")
        tts = gTTS(text=texto_audio, lang="es", slow=False)

        temp_path = f"/tmp/bdo_{uuid.uuid4().hex[:8]}.mp3"
        tts.save(temp_path)

        print("[tts] Subiendo a Cloudinary...")
        result = cloudinary.uploader.upload(
            temp_path,
            resource_type="video",
            folder="bdo_voice",
            public_id=f"response_{uuid.uuid4().hex[:8]}",
            overwrite=True,
        )

        os.unlink(temp_path)
        audio_url = result.get("secure_url", "")
        print(f"[tts] Audio disponible en: {audio_url}")
        return audio_url

    except Exception as e:
        print(f"[tts] Error generando audio: {e}")
        return None
