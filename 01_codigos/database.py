"""
database.py — Operaciones con Supabase
Gestiona usuarios y conversaciones persistentes por usuario.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# ── Conexión a Supabase ─────────────────────────────────────
_client: Optional[Client] = None


def get_client() -> Client:
    """Retorna el cliente de Supabase (singleton)."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            raise ValueError(
                "SUPABASE_URL y SUPABASE_KEY son requeridos en .env"
            )
        _client = create_client(url, key)
    return _client


# ══════════════════════════════════════════════════════════
# USUARIOS
# ══════════════════════════════════════════════════════════

def get_or_create_user(email: str) -> tuple[dict, bool]:
    """
    Obtiene un usuario por email o lo crea si no existe.

    Retorna:
        (user_dict, is_new_user)
        - user_dict: datos del usuario de Supabase
        - is_new_user: True si acaba de ser creado
    """
    db = get_client()
    email = email.strip().lower()

    # Intentar obtener usuario existente
    result = db.table("usuarios")\
        .select("*")\
        .eq("email", email)\
        .execute()

    if result.data:
        user = result.data[0]
        is_new = False

        # Actualizar última sesión
        db.table("usuarios")\
            .update({"ultima_sesion": datetime.now(timezone.utc).isoformat()})\
            .eq("email", email)\
            .execute()

        # Si ya existía, marcar como no nuevo en próximas sesiones
        if user.get("es_nuevo"):
            db.table("usuarios")\
                .update({"es_nuevo": False})\
                .eq("email", email)\
                .execute()
            is_new = True  # La primera vez siempre es nueva
        
        return user, is_new
    else:
        # Crear nuevo usuario
        nombre = email.split("@")[0].replace(".", " ").title()
        new_user = {
            "email":         email,
            "nombre":        nombre,
            "es_nuevo":      True,
            "creado_en":     datetime.now(timezone.utc).isoformat(),
            "ultima_sesion": datetime.now(timezone.utc).isoformat(),
        }
        result = db.table("usuarios").insert(new_user).execute()
        return result.data[0], True


# ══════════════════════════════════════════════════════════
# CONVERSACIONES
# ══════════════════════════════════════════════════════════

def _msgs_to_json(messages: list) -> list[dict]:
    """Convierte HumanMessage/AIMessage a lista serializable."""
    out = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            out.append({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            out.append({"type": "ai", "content": msg.content})
    return out


def _json_to_msgs(data: list[dict]) -> list:
    """Convierte lista JSON a HumanMessage/AIMessage."""
    msgs = []
    for item in data:
        t = item.get("type", "")
        c = item.get("content", "")
        if t == "human":
            msgs.append(HumanMessage(content=c))
        elif t == "ai":
            msgs.append(AIMessage(content=c))
    return msgs


def load_conversation(email: str, window_k: int = 6) -> list:
    """
    Carga el historial de conversación de un usuario desde Supabase.
    Aplica la ventana deslizante de k turnos.

    Retorna: lista de HumanMessage/AIMessage
    """
    db    = get_client()
    email = email.strip().lower()

    result = db.table("conversaciones")\
        .select("mensajes")\
        .eq("email_usuario", email)\
        .execute()

    if not result.data:
        return []

    raw_msgs = result.data[0].get("mensajes", [])
    msgs     = _json_to_msgs(raw_msgs)

    # Aplicar ventana k (los últimos k*2 mensajes)
    return msgs[-(window_k * 2):]


def save_conversation(email: str, messages: list) -> None:
    """
    Guarda el historial de conversación en Supabase.
    Usa UPSERT para crear o actualizar.
    """
    db      = get_client()
    email   = email.strip().lower()
    payload = _msgs_to_json(messages)

    # Verificar si ya existe
    result = db.table("conversaciones")\
        .select("id")\
        .eq("email_usuario", email)\
        .execute()

    if result.data:
        # Actualizar registro existente
        db.table("conversaciones")\
            .update({"mensajes": payload})\
            .eq("email_usuario", email)\
            .execute()
    else:
        # Crear nuevo registro
        db.table("conversaciones")\
            .insert({"email_usuario": email, "mensajes": payload})\
            .execute()


def clear_conversation(email: str) -> None:
    """Borra el historial de conversación de un usuario."""
    db    = get_client()
    email = email.strip().lower()

    db.table("conversaciones")\
        .delete()\
        .eq("email_usuario", email)\
        .execute()


def get_stats() -> dict:
    """Estadísticas generales del sistema (para el panel de admin)."""
    db = get_client()

    users_count = db.table("usuarios").select("id", count="exact").execute()
    conv_count  = db.table("conversaciones").select("id", count="exact").execute()

    return {
        "total_usuarios":      users_count.count or 0,
        "total_conversaciones": conv_count.count or 0,
    }
