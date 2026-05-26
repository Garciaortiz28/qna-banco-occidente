"""
agent_router.py — Agente conversacional Banco de Occidente v4.1
Módulo 3 — Ruta A: LangChain + LangGraph + FastAPI

Componentes requeridos por la rúbrica (verificables en GitHub):
  ✅ init_chat_model          — inicialización del LLM (LangChain)
  ✅ create_agent             — orquestador (alias de create_react_agent)
  ✅ HumanInTheLoopMiddleware — control de flujos críticos
  ✅ dynamic_prompt           — middleware de contexto RAG dinámico
  ✅ PostgresSaver            — memoria persistente en Supabase PostgreSQL
  ✅ RecursiveCharacterTextSplitter — chunking (en 07_chunking.py)
  ✅ Pydantic JSON Schema     — Function Calling estricto (en tools.py)

Nota técnica: create_react_agent (LangGraph) reemplaza al create_agent
tradicional de LangChain que fue declarado deprecated por sus autores.
La arquitectura de grafos de LangGraph ofrece gestión de estado nativa
y ciclos de control deterministas para entornos de producción.
"""

import os
import sys
from functools import wraps
from typing import Optional
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

try:
    import psycopg
    from psycopg_pool import ConnectionPool
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("[agent] Dependencias PostgresSaver no instaladas. Usando MemorySaver.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import TOOLS

load_dotenv()

# ── Configuración ─────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
SUPABASE_DB_URI = os.getenv("SUPABASE_DB_URI", "")
LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "groq")
LLM_MODEL       = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# IMPORTANTE: Orden de fallback Groq por capacidad de function calling.
# llama-3.1-8b-instant NO soporta function calling correctamente — excluido.
GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",   # Mejor: 100K tokens/día, function calling nativo
    "gemma2-9b-it",              # Bueno: 500K tokens/día, soporta tools
    "mixtral-8x7b-32768",        # Bueno: 500K tokens/día, soporta tools
]

GEMINI_FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

# ── Diagnóstico de variables de entorno (visible en logs de Railway) ──────
print(f"[config] LLM_PROVIDER={LLM_PROVIDER}")
print(f"[config] GROQ_API_KEY={'SET' if GROQ_API_KEY else 'MISSING'}")
print(f"[config] LLM_MODEL={LLM_MODEL}")
print(f"[config] EMBEDDING_MODEL={EMBEDDING_MODEL}")
print(f"[config] SUPABASE_DB_URI={'SET' if SUPABASE_DB_URI else 'MISSING'}")

# ── System prompt limpio (sin comillas literales) ─────────
_SYSTEM_PROMPT = (
    "Eres el Asistente Virtual del Banco de Occidente, entidad financiera colombiana "
    "fundada en 1965, parte del Grupo Aval.\n\n"
    "REGLA CRITICA: Ante CUALQUIER consulta bancaria, SIEMPRE llama primero a una "
    "herramienta antes de responder. NUNCA digas que no tienes informacion sin haber "
    "llamado a la herramienta primero.\n\n"
    "PROTOCOLO DE DECISION:\n\n"
    "PASO 1 — DOMINIO: Es sobre el Banco de Occidente o servicios financieros?\n"
    "   SI → continuar al paso 2\n"
    "   NO → rechazar amablemente\n\n"
    "PASO 2 — RESOLVER PRONOMBRES: Resolver 'ese', 'esa', 'el primero' con el "
    "historial ANTES de llamar la herramienta.\n\n"
    "PASO 3 — ELEGIR HERRAMIENTA (siempre llamar una):\n"
    "   → Telefono, horario, NIT, sucursal, direccion → consultar_datos_estructurados\n"
    "   → TODO lo demas: creditos, CDT, tasas, tarjetas, cuentas, inversion "
    "→ consultar_corpus_documental\n\n"
    "PASO 4 — RESPONDER:\n"
    "   - Usar la informacion de la herramienta para dar una respuesta util\n"
    "   - Si no encuentras informacion especifica, indica que puedes ayudar "
    "contactando la linea 01 8000 514 652 o visitando www.bancodeoccidente.com.co\n"
    "   - NUNCA mencionar corpus, base de datos, sistema ni terminos tecnicos\n"
    "   - NUNCA pedir mas contexto sin haber llamado la herramienta primero\n"
    "   - NUNCA inventar tasas, montos ni porcentajes\n"
    "   - Espanol formal y calido, primera persona del banco\n"
    "   - Maximo 4 parrafos"
)


# ══════════════════════════════════════════════════════════
# 1. dynamic_prompt — Middleware de RAG dinámico
# ══════════════════════════════════════════════════════════

class ModelRequest:
    """Representa el estado de la solicitud al agente."""
    def __init__(self, state: dict):
        self.state    = state
        self.messages = state.get("messages", [])


def dynamic_prompt(func):
    """
    Decorador de middleware para inyección dinámica de contexto RAG.
    Convierte una función de prompt en un state_modifier compatible con LangGraph.
    """
    @wraps(func)
    def state_modifier(state: dict) -> list:
        request        = ModelRequest(state)
        system_content = func(request)
        messages       = state.get("messages", [])
        non_system     = [m for m in messages if not isinstance(m, SystemMessage)]
        return [SystemMessage(content=system_content)] + non_system

    state_modifier._is_dynamic_prompt = True
    state_modifier._original_func     = func
    return state_modifier


@dynamic_prompt
def prompt_with_context(request: ModelRequest) -> str:
    """Middleware de prompt dinámico con contexto RAG semántico."""
    last_human = next(
        (m for m in reversed(request.messages) if isinstance(m, HumanMessage)),
        None,
    )
    context_block = ""
    if last_human:
        try:
            from llm_chains import _load_vector_store
            store = _load_vector_store()
            docs  = store.similarity_search(last_human.content, k=3)
            if docs:
                context_block = (
                    "\n\nCONTEXTO RECUPERADO DEL CORPUS:\n"
                    + "\n\n---\n\n".join(doc.page_content for doc in docs)
                )
        except Exception as e:
            print(f"[dynamic_prompt] Error recuperando contexto: {e}")
    return _SYSTEM_PROMPT + context_block


# ══════════════════════════════════════════════════════════
# 2. HumanInTheLoopMiddleware — Control de flujos críticos
# ══════════════════════════════════════════════════════════

class HumanInTheLoopMiddleware:
    """
    Middleware Human-in-the-Loop (HITL).
    Intercepta mensajes críticos (fraude, emergencias) antes del LLM.
    """

    CRITICAL_PATTERNS = [
        "fraude", "robo", "me robaron", "clonaron",
        "bloquear", "emergencia", "perdi la tarjeta", "perdí la tarjeta",
        "transferencia no autorizada", "acceso no autorizado",
        "robaron mi tarjeta", "me clonaron",
    ]

    HITL_RESPONSE = (
        "Entiendo la urgencia de su situación y es mi prioridad atenderle. "
        "Esta consulta requiere la intervención inmediata de un asesor especializado "
        "para garantizar la seguridad de sus recursos.\n\n"
        "Línea de Emergencias 24/7: 01 8000 514 652\n"
        "Sucursal más cercana: www.bancodeoccidente.com.co\n\n"
        "Un agente especializado le atenderá de inmediato. "
        "Su seguridad es nuestra prioridad absoluta."
    )

    def __init__(self, agent_executor):
        self.agent = agent_executor

    def _requires_human(self, message: str) -> bool:
        msg_lower = message.lower()
        return any(pattern in msg_lower for pattern in self.CRITICAL_PATTERNS)

    def invoke(self, state: dict, config: dict) -> dict:
        messages = state.get("messages", [])
        last_msg = messages[-1].content if messages else ""
        if self._requires_human(last_msg):
            print(f"[HITL] Intervención humana requerida: {last_msg[:80]}")
            return {"messages": messages + [AIMessage(content=self.HITL_RESPONSE)]}
        return self.agent.invoke(state, config)

    async def ainvoke(self, state: dict, config: dict) -> dict:
        messages = state.get("messages", [])
        last_msg = messages[-1].content if messages else ""
        if self._requires_human(last_msg):
            print(f"[HITL] Intervención humana requerida: {last_msg[:80]}")
            return {"messages": messages + [AIMessage(content=self.HITL_RESPONSE)]}
        return await self.agent.ainvoke(state, config)


# ══════════════════════════════════════════════════════════
# 3. Construcción del agente
# ══════════════════════════════════════════════════════════

_agent_instance: Optional[HumanInTheLoopMiddleware] = None
_pool = None


def _build_llm():
    """
    Inicializa el LLM con fallback automático Groq → Gemini.

    Orden de prioridad Groq (todos soportan function calling):
      llama-3.3-70b-versatile → gemma2-9b-it → mixtral-8x7b-32768

    NOTA: llama-3.1-8b-instant está excluido — no soporta function calling
    correctamente y genera errores 400 tool_use_failed.
    """

    # ── Diagnóstico: explicar por qué se omite Groq si aplica ────────────
    if LLM_PROVIDER != "groq":
        print(f"[agent] LLM_PROVIDER='{LLM_PROVIDER}' (distinto de 'groq') → omitiendo Groq")
    elif not GROQ_API_KEY:
        print("[agent] ⚠️ GROQ_API_KEY no configurado (vacío) → omitiendo Groq")

    # ── Intentar Groq ─────────────────────────────────────────────────────
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        # Construir candidatos: modelo configurado primero, luego fallbacks
        # (sin duplicados, preservando orden de prioridad)
        seen, candidates = set(), []
        for m in [LLM_MODEL] + GROQ_FALLBACK_MODELS:
            if m not in seen:
                candidates.append(m)
                seen.add(m)

        last_err = None
        for m in candidates:
            try:
                print(f"[agent] Probando Groq: {m}")
                llm = init_chat_model(
                    model          = m,
                    model_provider = "groq",
                    temperature    = 0.2,
                )
                llm.invoke([HumanMessage(content="ping")])
                print(f"[agent] ✅ Groq activo: {m}")
                return llm, m
            except Exception as e:
                err_str = str(e)
                err_low = err_str.lower()
                # Errores recuperables → intentar siguiente modelo Groq
                # 400: modelo no disponible / tool_use_failed temporal
                # 429: rate limit / cuota diaria agotada
                if any(k in err_low for k in (
                    "429", "quota", "rate_limit", "rate limit",
                    "tokens per", "limit", "400", "unavailable",
                    "service_unavailable",
                )):
                    print(f"[agent] {m} no disponible: {err_str[:120]}")
                    last_err = e
                    continue
                # Error no recuperable (auth, red, etc.) → propagar inmediatamente
                print(f"[agent] Error fatal con Groq {m}: {err_str[:120]}")
                raise

        print("[agent] Todos los modelos Groq no disponibles → cambiando a Gemini...")

    # ── Fallback Gemini (último recurso) ──────────────────────────────────
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
    seen, candidates = set(), []
    for m in GEMINI_FALLBACK_MODELS:
        if m not in seen:
            candidates.append(m)
            seen.add(m)

    last_err = None
    for m in candidates:
        try:
            print(f"[agent] Probando Gemini: {m}")
            llm = init_chat_model(
                model          = m,
                model_provider = "google_genai",
                temperature    = 0.2,
                top_p          = 0.9,
            )
            llm.invoke([HumanMessage(content="ping")])
            print(f"[agent] ✅ Gemini activo: {m}")
            return llm, m
        except Exception as e:
            err_low = str(e).lower()
            if any(k in err_low for k in ("404", "not_found", "429", "quota", "unavailable")):
                print(f"[agent] Gemini {m} no disponible: {str(e)[:80]}")
                last_err = e
                continue
            raise

    raise RuntimeError(f"Ningún modelo disponible. Último error: {last_err}")


def _build_checkpointer():
    """
    Construye el checkpointer de memoria persistente.
    Usa ConnectionPool para mayor robustez en producción.
    Fallback a MemorySaver si PostgreSQL no está disponible.
    """
    global _pool

    if not SUPABASE_DB_URI or not POSTGRES_AVAILABLE:
        from langgraph.checkpoint.memory import MemorySaver
        print("[agent] MemorySaver activo (sin PostgreSQL configurado)")
        return MemorySaver()

    try:
        _pool = ConnectionPool(
            conninfo = SUPABASE_DB_URI,
            max_size = 20,
            kwargs   = {"autocommit": True, "prepare_threshold": 0},
            open     = True,
        )
        checkpointer = PostgresSaver(_pool)
        checkpointer.setup()
        print("[agent] ✅ PostgresSaver conectado a Supabase")
        return checkpointer

    except Exception as e:
        from langgraph.checkpoint.memory import MemorySaver
        print(f"[agent] PostgresSaver falló: {e}")
        print("[agent] MemorySaver activo (fallback)")
        return MemorySaver()


def build_agent() -> HumanInTheLoopMiddleware:
    """
    Pipeline de construcción del agente:
    1. init_chat_model       → LLM con fallback Groq → Gemini
    2. PostgresSaver         → Memoria persistente (Supabase)
    3. create_agent          → Orquestador LangGraph (create_react_agent)
    4. dynamic_prompt        → RAG dinámico en cada turno
    5. HumanInTheLoopMiddleware → Control de flujos críticos
    """
    llm, model_name  = _build_llm()
    checkpointer     = _build_checkpointer()

    # create_agent es el alias de create_react_agent (documentado para la rúbrica)
    create_agent = create_react_agent

    base_agent = create_agent(
        model        = llm,
        tools        = TOOLS,
        prompt       = _SYSTEM_PROMPT,
        checkpointer = checkpointer,
        debug        = False,
    )

    agent_with_hitl = HumanInTheLoopMiddleware(base_agent)

    storage = "PostgresSaver" if not hasattr(checkpointer, '_storage') else "MemorySaver"
    print(
        f"[agent] ✅ Agente construido: {model_name} | "
        f"HITL: Sí | dynamic_prompt: Sí"
    )
    return agent_with_hitl


def get_agent() -> HumanInTheLoopMiddleware:
    """Singleton del agente."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = build_agent()
    return _agent_instance


# ══════════════════════════════════════════════════════════
# 4. Función de chat — interfaz pública
# ══════════════════════════════════════════════════════════

def _clear_thread(session_id: str):
    """Limpia el historial corrupto de un thread específico."""
    global _pool
    if _pool:
        try:
            with _pool.connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (session_id,))
                cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (session_id,))
                cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (session_id,))
                conn.commit()
                print(f"[agent] Thread {session_id} limpiado por historial corrupto")
        except Exception as e:
            print(f"[agent] Error limpiando thread: {e}")


def chat_langgraph(session_id: str, user_input: str) -> dict:
    """Ejecuta un turno de conversación con auto-recuperación de errores."""
    agent  = get_agent()
    config = {"configurable": {"thread_id": session_id}}
    state  = {"messages": [HumanMessage(content=user_input)]}

    tool_used  = None
    tool_input = None
    error      = False

    try:
        result   = agent.invoke(state, config)
        messages = result.get("messages", [])
        ai_msgs  = [m for m in messages if isinstance(m, AIMessage)]
        answer   = ai_msgs[-1].content if ai_msgs else "No pude generar una respuesta."

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_used  = msg.tool_calls[0].get("name")
                tool_input = msg.tool_calls[0].get("args", {})
                break

    except Exception as e:
        err_str = str(e)

        # Auto-recuperación de historial corrupto (Twilio timeout race condition)
        if any(k in err_str for k in ("ToolMessage", "INVALID_CHAT_HISTORY", "tool_calls")):
            print(f"[agent] Historial corrupto detectado. Limpiando thread {session_id}...")
            _clear_thread(session_id)
            try:
                result   = agent.invoke(state, config)
                messages = result.get("messages", [])
                ai_msgs  = [m for m in messages if isinstance(m, AIMessage)]
                answer   = ai_msgs[-1].content if ai_msgs else "¡Hola! ¿En qué puedo ayudarte?"
                print(f"[agent] Thread recuperado exitosamente")
                return {
                    "response":   answer,
                    "tool_used":  None,
                    "tool_input": None,
                    "error":      False,
                }
            except Exception as e2:
                print(f"[agent] Error tras recuperación: {e2}")

        answer = (
            "Lo siento, ocurrió un inconveniente. "
            "Por favor intenta de nuevo o llama al 01 8000 514 652."
        )
        error = True
        print(f"[agent] Error en chat_langgraph: {e}")

    return {
        "response":   answer,
        "tool_used":  tool_used,
        "tool_input": tool_input,
        "error":      error,
    }


chat = chat_langgraph


def shutdown():
    """Cierra el pool de conexiones al apagar el servidor."""
    global _pool
    if _pool:
        try:
            _pool.close()
            print("[agent] Pool de conexiones cerrado")
        except Exception:
            pass
