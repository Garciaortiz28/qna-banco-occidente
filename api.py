"""
api.py — API REST Asistente Virtual Banco de Occidente v4.2
FastAPI · LangGraph · Function Calling · PostgresSaver · WhatsApp

Endpoints:
  POST   /chat           — Endpoint principal (WhatsApp, N8N, clientes)
  GET    /health         — Estado del servicio
  GET    /stats          — Estadisticas en tiempo real
  POST   /webhook/twilio — Webhook directo de Twilio WhatsApp
  GET    /session/{id}   — Info de sesion
  DELETE /session/{id}   — Limpiar sesion

Cambios v4.2:
- Pre-carga del agente y embeddings al arrancar (evita Twilio timeout en cold start)
- Shutdown limpio del pool de conexiones PostgreSQL
"""

import os
import sys
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response as FastResponse
from pydantic import BaseModel, Field
import uvicorn

ROOT    = Path(__file__).parent
CODIGOS = ROOT / "01_codigos"
sys.path.insert(0, str(CODIGOS))

from agent_router import chat_langgraph, get_agent, shutdown  # type: ignore

_stats = {
    "total_requests": 0,
    "total_errors":   0,
    "start_time":     time.time(),
}


# ══════════════════════════════════════════════════════════
# Modelos Pydantic
# ══════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=200)
    message:    str = Field(..., min_length=1, max_length=2000)
    channel:    str = Field(default="api")


class ChatResponse(BaseModel):
    session_id:       str
    response:         str
    tool_used:        Optional[str]  = None
    tool_input:       Optional[dict] = None
    channel:          str            = "api"
    response_time_ms: float          = 0.0
    error:            bool           = False


class HealthResponse(BaseModel):
    status:   str
    uptime_s: float
    requests: int
    errors:   int
    agent:    str


# ══════════════════════════════════════════════════════════
# Lifespan — pre-carga al arrancar
# ══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Asistente Virtual BdO — API iniciada")

    try:
        print("[startup] Pre-cargando agente...")
        await asyncio.to_thread(get_agent)
        print("[startup] ✅ Agente listo")
        print("[startup] Pre-cargando embeddings (90MB, rapido)...")
        from llm_chains import _load_vector_store  # type: ignore
        await asyncio.to_thread(_load_vector_store)
        print("[startup] ✅ Embeddings listos")
        print("[startup] ✅ Sistema listo para recibir mensajes")
    except Exception as e:
        print(f"[startup] ⚠️ Error en pre-carga: {e}")

    yield

    print("🛑 Cerrando API...")
    shutdown()


# ══════════════════════════════════════════════════════════
# App FastAPI
# ══════════════════════════════════════════════════════════

app = FastAPI(
    title       = "Asistente Virtual Banco de Occidente",
    description = "API REST · LangGraph · PostgresSaver · HumanInTheLoopMiddleware · dynamic_prompt",
    version     = "4.2.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["GET", "POST", "DELETE"],
    allow_headers = ["*"],
)


# ══════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════

@app.get("/", tags=["Info"])
async def root():
    return {
        "service": "Asistente Virtual Banco de Occidente",
        "version": "4.2.0",
        "stack":   "LangGraph + FastAPI + PostgresSaver + Twilio + Groq",
        "docs":    "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health():
    return HealthResponse(
        status   = "ok",
        uptime_s = round(time.time() - _stats["start_time"], 1),
        requests = _stats["total_requests"],
        errors   = _stats["total_errors"],
        agent    = "LangGraph · init_chat_model · PostgresSaver · HITL · dynamic_prompt",
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    t0 = time.time()
    _stats["total_requests"] += 1

    session_id = request.session_id.strip()
    message    = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio.")

    try:
        result     = await asyncio.to_thread(chat_langgraph, session_id, message)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        if result.get("error"):
            _stats["total_errors"] += 1

        return ChatResponse(
            session_id       = session_id,
            response         = result["response"],
            tool_used        = result.get("tool_used"),
            tool_input       = result.get("tool_input") if isinstance(result.get("tool_input"), dict) else None,
            channel          = request.channel,
            response_time_ms = elapsed_ms,
            error            = result.get("error", False),
        )
    except Exception as e:
        _stats["total_errors"] += 1
        print(f"[api] Error para {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)[:300]}")


async def _process_voice_background(from_number: str, media_url: str, to_number: str):
    """Procesa la nota de voz en segundo plano y envía respuesta via Twilio API."""
    import os
    from twilio.rest import Client

    account_sid   = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token    = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    twilio_client = Client(account_sid, auth_token)

    try:
        # 1. Transcribir
        from transcription import transcribe_whatsapp_audio
        texto = await asyncio.to_thread(transcribe_whatsapp_audio, media_url)
        if not texto:
            texto = "Hola, ¿en qué puedo ayudarte?"
        print(f"[voice_bg] Transcripción: '{texto[:80]}'")

        # 2. Procesar con el agente
        result = await asyncio.to_thread(chat_langgraph, from_number, texto)
        response_text = result["response"]

        # 3. Generar audio (opcional)
        audio_url = None
        try:
            from tts_service import text_to_audio_url
            audio_url = await asyncio.to_thread(text_to_audio_url, response_text)
        except Exception as e:
            print(f"[voice_bg] TTS fallido (enviando solo texto): {e}")

        # 4. Enviar respuesta via Twilio API
        msg_params = {
            "from_": from_whatsapp,
            "to": from_number,
            "body": response_text[:1600],
        }
        if audio_url:
            msg_params["media_url"] = [audio_url]

        twilio_client.messages.create(**msg_params)
        print(f"[voice_bg] Respuesta enviada a {from_number}")

    except Exception as e:
        print(f"[voice_bg] Error: {e}")
        try:
            twilio_client.messages.create(
                from_=from_whatsapp,
                to=from_number,
                body="Lo siento, no pude procesar tu nota de voz. Escríbeme el texto o llama al 01 8000 514 652.",
            )
        except Exception:
            pass


@app.post("/webhook/twilio", tags=["WhatsApp"])
async def twilio_webhook(request: Request):
    """
    Webhook Twilio WhatsApp con soporte de notas de voz.
    Texto normal: procesa con timeout 13s.
    Nota de voz: ACK inmediato + procesamiento en background via Twilio REST API.
    """
    import urllib.parse

    body = await request.body()
    data = dict(urllib.parse.parse_qsl(body.decode("utf-8")))

    from_number  = data.get("From", "")
    message_body = data.get("Body", "").strip()
    media_url    = data.get("MediaUrl0", "")
    media_type   = data.get("MediaContentType0", "")

    if not from_number:
        return JSONResponse(content={"status": "ignored"})

    is_voice_note = bool(media_url and "audio" in media_type.lower())

    # NOTAS DE VOZ: responder inmediatamente + procesar en background
    if is_voice_note:
        print(f"[webhook] Nota de voz de {from_number} — lanzando background task")
        asyncio.create_task(
            _process_voice_background(from_number, media_url, from_number)
        )
        twiml_ack = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '    <Message><Body>\U0001f3a4 Recibí tu nota de voz, '
            'dame un momento para escucharte...</Body></Message>\n'
            '</Response>'
        )
        return FastResponse(content=twiml_ack, media_type="application/xml")

    # TEXTO: procesar con timeout como antes
    if not message_body:
        return JSONResponse(content={"status": "ignored"})

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(chat_langgraph, from_number, message_body),
            timeout=13.0,
        )
        response_text = result["response"]
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Message><Body>{response_text[:1600]}</Body></Message>\n'
            '</Response>'
        )
        return FastResponse(content=twiml, media_type="application/xml")

    except asyncio.TimeoutError:
        print(f"[webhook/twilio] Timeout 13s — {from_number}")
        twiml_timeout = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '    <Message><Body>Estoy procesando tu consulta. '
            'Por favor envía el mensaje nuevamente en unos segundos.</Body></Message>\n'
            '</Response>'
        )
        return FastResponse(content=twiml_timeout, media_type="application/xml")

    except Exception as e:
        print(f"[webhook/twilio] Error: {e}")
        error_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '    <Message><Body>Lo siento, ocurrió un inconveniente. '
            'Por favor llama al 01 8000 514 652.</Body></Message>\n'
            '</Response>'
        )
        return FastResponse(content=error_twiml, media_type="application/xml")


@app.get("/session/{session_id}", tags=["Sesiones"])
async def get_session_info(session_id: str):
    return {
        "session_id": session_id,
        "storage":    "PostgresSaver (Supabase PostgreSQL)",
        "note":       "Ver tabla checkpoints en Supabase para historial completo.",
    }


@app.delete("/session/{session_id}", tags=["Sesiones"])
async def clear_session(session_id: str):
    try:
        from agent_router import _clear_thread  # type: ignore
        _clear_thread(session_id)
        return {"cleared": True, "session_id": session_id}
    except Exception as e:
        return {"cleared": False, "session_id": session_id, "error": str(e)}


@app.get("/stats", tags=["Info"])
async def get_stats():
    return {
        "api_requests":   _stats["total_requests"],
        "api_errors":     _stats["total_errors"],
        "uptime_minutes": round((time.time() - _stats["start_time"]) / 60, 1),
        "agent_stack":    "LangGraph + PostgresSaver + HumanInTheLoopMiddleware + dynamic_prompt",
    }


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host      = "0.0.0.0",
        port      = int(os.getenv("PORT", 8000)),
        reload    = False,
        log_level = "info",
    )
