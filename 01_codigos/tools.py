"""
tools.py — Herramientas del agente con Function Calling estricto
Cada herramienta tiene un JSON Schema Pydantic que fuerza al LLM
a generar parámetros correctos y tipados.
"""

import os
import sys
import json
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

# ══════════════════════════════════════════════════════════
# JSON SCHEMAS — FUNCTION CALLING ESTRICTO
# ══════════════════════════════════════════════════════════

class ConsultaCorpusInput(BaseModel):
    """Schema estricto para búsqueda en el corpus documental bancario."""

    consulta: str = Field(
        ...,
        description=(
            "Consulta específica y clara sobre productos, servicios o información "
            "del Banco de Occidente. "
            "CRÍTICO: Resuelve TODOS los pronombres usando el historial antes de "
            "invocar esta función. "
            "❌ MAL: '¿requisitos de ese?' "
            "✅ BIEN: '¿requisitos crédito hipotecario Banco de Occidente?'"
        ),
        min_length=5,
        max_length=500,
        examples=[
            "requisitos crédito hipotecario",
            "tarjetas de crédito disponibles y beneficios",
            "cómo abrir cuenta de ahorros",
        ],
    )


class ConsultaEstructuradaInput(BaseModel):
    """Schema estricto para consulta de datos puntuales del banco."""

    tipo: Literal[
        "telefono",
        "horario",
        "corporativo",
        "sucursales",
        "redes_sociales",
        "canales_digitales",
        "normativo",
        "preguntas_directas",
    ] = Field(
        ...,
        description=(
            "Categoría exacta del dato a consultar. Elige SOLO uno de los "
            "valores permitidos:\n"
            "- telefono: líneas de atención al cliente\n"
            "- horario: horarios de atención de sucursales y canales\n"
            "- corporativo: NIT, razón social, datos legales\n"
            "- sucursales: listado de oficinas (usar campo 'ciudad' para filtrar)\n"
            "- redes_sociales: Facebook, Instagram, YouTube, etc.\n"
            "- canales_digitales: app móvil, banca web, etc.\n"
            "- normativo: regulaciones, supervisión, SARLAFT\n"
            "- preguntas_directas: tutoriales rápidos (bloqueo tarjeta, clave)"
        ),
    )

    ciudad: str = Field(
        default="",
        description=(
            "Ciudad para filtrar resultados. Solo aplica cuando tipo='sucursales'. "
            "Ejemplos: 'Cali', 'Bogotá', 'Medellín'. Dejar vacío para todas."
        ),
        examples=["Cali", "Bogotá", "Medellín", "Barranquilla"],
    )


# ══════════════════════════════════════════════════════════
# HERRAMIENTAS
# ══════════════════════════════════════════════════════════

@tool("consultar_corpus_documental", args_schema=ConsultaCorpusInput, return_direct=False)
def consultar_corpus_documental(consulta: str) -> str:
    """
    Busca información NARRATIVA en el corpus documental del Banco de Occidente.

    Usar cuando el usuario pregunta sobre:
    - Características y beneficios de productos (créditos, tarjetas, cuentas, CDTs)
    - Requisitos y procesos de solicitud
    - Historia, misión y valores corporativos del banco
    - Información general que requiere explicación extensa

    NO usar para: teléfonos, horarios, NIT, sucursales o datos puntuales.
    """
    try:
        from llm_chains import ask_question
        resultado = ask_question(consulta)
        if not resultado:
            return (
                "No encontré información específica sobre ese tema en el corpus. "
                "Puedo ayudarte consultando directamente con nuestros asesores."
            )
        return resultado
    except Exception as e:
        return (
            f"En este momento no pude acceder al corpus documental. "
            f"Te recomiendo contactarnos en: 01 8000 514 652. (Error interno: {str(e)[:60]})"
        )


@tool("consultar_datos_estructurados", args_schema=ConsultaEstructuradaInput, return_direct=False)
def consultar_datos_estructurados(
    tipo: str,
    ciudad: str = "",
) -> str:
    """
    Consulta datos PUNTUALES y PRECISOS del Banco de Occidente desde base de datos estructurada.

    Usar cuando el usuario pregunta por:
    - Teléfonos y líneas de atención
    - Horarios de sucursales o canales
    - NIT, razón social, datos corporativos
    - Ubicación de sucursales (por ciudad)
    - Redes sociales y canales digitales
    - Normativa y regulaciones
    - Tutoriales rápidos (bloquear tarjeta, recuperar clave)

    NO usar para: explicaciones de productos o información narrativa.
    """
    try:
        # Cargar JSON estructurado
        base_dir  = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "..", "data", "07_estructurado", "banco_info.json")

        with open(json_path, "r", encoding="utf-8") as f:
            banco_info = json.load(f)

        tipo_key = tipo.strip().lower()

        # Mapping de tipos a secciones del JSON
        tipo_map = {
            "telefono":         "lineas_atencion",
            "horario":          "horarios",
            "corporativo":      "informacion_corporativa",
            "sucursales":       "sucursales_principales",
            "redes_sociales":   "redes_sociales",
            "canales_digitales":"canales_digitales",
            "normativo":        "datos_normativos",
            "preguntas_directas":"preguntas_frecuentes_directas",
        }

        if tipo_key not in tipo_map:
            return (
                f"Tipo de consulta '{tipo}' no reconocido. "
                f"Tipos válidos: {', '.join(tipo_map.keys())}"
            )

        seccion = tipo_map[tipo_key]
        datos   = banco_info.get(seccion, {})

        if not datos:
            return (
                f"No encontré datos en la categoría '{tipo}'. "
                "Te invito a contactarnos en: 01 8000 514 652."
            )

        # Filtrar por ciudad si aplica
        if tipo_key == "sucursales" and ciudad:
            ciudad_norm = ciudad.strip().lower()
            if isinstance(datos, list):
                filtradas = [
                    s for s in datos
                    if ciudad_norm in str(s.get("ciudad", "")).lower()
                ]
                datos = filtradas if filtradas else datos

        # Formatear respuesta
        if isinstance(datos, dict):
            lineas = [f"• {k}: {v}" for k, v in datos.items()]
            return "\n".join(lineas)
        elif isinstance(datos, list):
            lineas = []
            for item in datos:
                if isinstance(item, dict):
                    lineas.append(" | ".join(f"{k}: {v}" for k, v in item.items()))
                else:
                    lineas.append(str(item))
            return "\n".join(lineas)
        else:
            return str(datos)

    except FileNotFoundError:
        return (
            "En este momento no pude acceder a los datos estructurados. "
            "Contacta nuestras líneas de atención: 01 8000 514 652."
        )
    except Exception as e:
        return (
            f"No pude obtener esa información en este momento. "
            f"Por favor intenta de nuevo o llama al 01 8000 514 652. "
            f"(Error: {str(e)[:60]})"
        )


# Lista de tools exportada
TOOLS = [consultar_corpus_documental, consultar_datos_estructurados]
