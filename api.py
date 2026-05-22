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

    # Pre-cargar agente y embeddings para evitar Twilio timeout en cold start
    # Sin esto, el primer request puede tardar 60+ seg y Twilio cancela la conexion
    try:
        print("[startup] Pre-cargando agente...")
        await asyncio.to_thread(get_agent)
        print("[startup] ✅ Agente listo")

        print("[startup] Pre-cargando embeddings...")
        from llm_chains import _load_vector_store  # type: ignore
        await asyncio.to_thread(_load_vector_store)
        print("[startup] ✅ Embeddings listos")

        print("[startup] ✅ Sistema listo para recibir mensajes")
    except Exception as e:
        print(f"[startup] ⚠️ Error en pre-carga: {e} — el sistema sigue funcionando")

    yield

    # Shutdown limpio
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


@app.post("/webhook/twilio", tags=["WhatsApp"])
async def twilio_webhook(request: Request):
    """
    Webhook Twilio WhatsApp Sandbox.
    Configurar en: Twilio Console → Sandbox Settings → When a message comes in
    URL: https://TU_DOMINIO/webhook/twilio (POST)
    """
    import urllib.parse

    body = await request.body()
    data = dict(urllib.parse.parse_qsl(body.decode("utf-8")))

    from_number  = data.get("From", "")
    message_body = data.get("Body", "").strip()

    if not from_number or not message_body:
        return JSONResponse(content={"status": "ignored"})

    try:
        result        = await asyncio.to_thread(chat_langgraph, from_number, message_body)
        response_text = result["response"]

        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Message><Body>{response_text[:1600]}</Body></Message>\n'
            '</Response>'
        )
        return FastResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        print(f"[webhook/twilio] Error: {e}")
        error_twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '    <Message><Body>Lo siento, ocurrio un inconveniente. '
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
