"""
diagnostico.py — Verificador del proyecto Banco de Occidente
Ejecutar desde la raíz del proyecto:
    python diagnostico.py
Pegar el resultado completo en el chat para diagnóstico.
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent
SEPARATOR = "=" * 65

def sep(title=""):
    if title:
        print(f"\n{'='*65}")
        print(f"  {title}")
        print(f"{'='*65}")
    else:
        print(f"\n{'-'*65}")

def check(label, exists, extra=""):
    icon = "✅" if exists else "❌"
    line = f"  {icon}  {label}"
    if extra:
        line += f"  →  {extra}"
    print(line)

def first_lines(path, n=3):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = [l.rstrip() for l in f.readlines()[:n] if l.strip()]
        return " | ".join(lines[:n])
    except Exception:
        return "[no se pudo leer]"

def grep(path, keyword):
    """Busca keyword en el archivo. Retorna True/False."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return keyword in f.read()
    except Exception:
        return False

def file_size(path):
    try:
        s = os.path.getsize(path)
        if s > 1024*1024:
            return f"{s/1024/1024:.1f} MB"
        elif s > 1024:
            return f"{s/1024:.1f} KB"
        return f"{s} B"
    except Exception:
        return "?"

# ══════════════════════════════════════════════════════════════
print(f"\n{SEPARATOR}")
print("  DIAGNÓSTICO DEL PROYECTO — Banco de Occidente")
print(f"  Ruta: {ROOT}")
print(f"{SEPARATOR}")

# ── RAÍZ DEL PROYECTO ────────────────────────────────────────
sep("1. ARCHIVOS EN LA RAÍZ")

raiz_files = {
    ".env":                "Variables de entorno (API keys)",
    ".env.example":        "Template del .env",
    ".gitignore":          "Excluye archivos sensibles",
    "pyproject.toml":      "Dependencias del proyecto",
    "uv.lock":             "Lock file de UV (AUTO)",
    "Makefile":            "Comandos del pipeline",
    "main.py":             "Orquestador CLI",
    "Procfile":            "Deploy en Railway (M3)",
    "api.py":              "FastAPI REST API (M3)",
    "chainlit_app.py":     "App Chainlit multiusuario (M2)",
    "chainlit.md":         "Bienvenida de Chainlit (M2)",
    "n8n_workflow.json":   "Workflow N8N (M3)",
    "supabase_setup.sql":  "SQL para Supabase (M2)",
}

for fname, desc in raiz_files.items():
    path = ROOT / fname
    exists = path.exists()
    extra = ""
    if exists:
        extra = file_size(path)
        if fname == "pyproject.toml":
            v = "v3.0.0" if grep(path, '3.0.0') else ("v2.0.0" if grep(path, '2.0.0') else "v1.x")
            extra += f" | versión detectada: {v}"
        if fname == "api.py":
            ok = grep(path, "FastAPI") and grep(path, "/chat")
            extra += " | endpoints OK" if ok else " | ⚠️ parece incompleto"
        if fname == ".env":
            keys = ["GEMINI_API_KEY","SUPABASE_URL","SUPABASE_KEY",
                    "TWILIO_ACCOUNT_SID","RESEND_API_KEY","LANGCHAIN_API_KEY"]
            found = [k for k in keys if grep(path, k)]
            missing = [k for k in keys if k not in found]
            extra += f" | keys OK: {len(found)}/6"
            if missing:
                extra += f" | FALTAN: {', '.join(missing)}"
    check(f"{fname:<28} ({desc})", exists, extra)

# ── .chainlit/ ────────────────────────────────────────────────
sep("2. .chainlit/")
for f in [".chainlit/config.toml"]:
    p = ROOT / f
    check(f, p.exists(), file_size(p) if p.exists() else "")

# ── .streamlit/ ───────────────────────────────────────────────
sep("3. .streamlit/")
for f in [".streamlit/config.toml"]:
    p = ROOT / f
    check(f, p.exists(), file_size(p) if p.exists() else "")

# ── public/ ───────────────────────────────────────────────────
sep("4. public/")
for f in ["public/custom.css", "public/voice.js"]:
    p = ROOT / f
    check(f, p.exists(), file_size(p) if p.exists() else "")

# ── 01_codigos/ ───────────────────────────────────────────────
sep("5. 01_codigos/")

codigos = {
    "config.py":               ("M1", None),
    "00_reset.py":             ("M1", None),
    "01_crawling.py":          ("M1", None),
    "02_scraping_selenium.py": ("M1", None),
    "03_cleaner.py":           ("M1", None),
    "04_markdown_builder.py":  ("M1", None),
    "05_corpus_master.py":     ("M1", None),
    "06_youtube_scraper.py":   ("M1", None),
    "07_chunking.py":          ("M3", "models/text-embedding-004"),
    "llm_chains.py":           ("M3", "models/text-embedding-004"),
    "tools.py":                ("M3", "ConsultaCorpusInput"),
    "agent_router.py":         ("M3", "error_occurred"),
    "database.py":             ("M2", "get_or_create_user"),
    "email_service.py":        ("M2", "send_welcome_email"),
    "tsne_analysis.py":        ("M3", "run_analysis"),
    "app.py":                  ("M1", None),
}

for fname, (mod, keyword) in codigos.items():
    p = ROOT / "01_codigos" / fname
    exists = p.exists()
    extra = f"[{mod}]"
    if exists:
        extra += f" {file_size(p)}"
        if keyword:
            ok = grep(p, keyword)
            extra += f" | versión {'✅ M3' if ok else '⚠️ VERSIÓN VIEJA — necesita reemplazo'}"
    check(f"01_codigos/{fname}", exists, extra)

# ── data/ ─────────────────────────────────────────────────────
sep("6. data/")

data_checks = [
    ("data/07_estructurado/banco_info.json", "banco_info.json con datos del banco"),
    ("data/08_chroma/chroma.sqlite3",        "Vector store ChromaDB"),
    ("data/06_corpus/corpus_master.md",      "Corpus maestro unificado"),
    ("data/memoria/sesion.json",             "Memoria persistente (se crea en primer uso)"),
]

for fpath, desc in data_checks:
    p = ROOT / fpath
    exists = p.exists()
    extra = ""
    if exists:
        extra = file_size(p)
        if "banco_info" in fpath:
            try:
                with open(p) as f:
                    data = json.load(f)
                keys = list(data.keys())
                extra += f" | secciones: {', '.join(keys[:4])}..."
            except Exception:
                extra += " | ⚠️ JSON inválido"
        if "sesion.json" in fpath:
            try:
                with open(p) as f:
                    data = json.load(f)
                n = len(data.get("messages", [])) // 2
                extra += f" | {n} turnos guardados"
            except Exception:
                extra += " | ⚠️ JSON inválido"
    check(f"{fpath}", exists, extra)

# ChromaDB chunk count
chroma_db = ROOT / "data" / "08_chroma"
if chroma_db.exists():
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_db))
        try:
            col = client.get_collection("banco_occidente")
            print(f"  📊 ChromaDB chunks indexados: {col.count()}")
        except Exception:
            print(f"  ⚠️  ChromaDB existe pero colección 'banco_occidente' no encontrada")
    except ImportError:
        print(f"  ℹ️  chromadb no instalado — no se puede verificar chunk count")

# ── DEPENDENCIAS INSTALADAS ───────────────────────────────────
sep("7. DEPENDENCIAS INSTALADAS")

deps = [
    ("fastapi",            "FastAPI REST API"),
    ("chainlit",           "Framework de chat"),
    ("supabase",           "Base de datos Supabase"),
    ("resend",             "Emails de bienvenida"),
    ("sklearn",            "scikit-learn para t-SNE"),
    ("plotly",             "Visualización t-SNE"),
    ("langsmith",          "Trazabilidad LangSmith"),
    ("langchain",          "LangChain core"),
    ("langchain_google_genai", "Gemini LLM + Embeddings"),
    ("chromadb",           "Vector store"),
    ("sentence_transformers", "Embeddings locales (legacy)"),
    ("uvicorn",            "Servidor ASGI para FastAPI"),
]

for pkg, desc in deps:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        check(f"{pkg:<28} ({desc})", True, f"v{ver}")
    except ImportError:
        check(f"{pkg:<28} ({desc})", False, "NO INSTALADO — ejecutar: uv sync")

# ── VARIABLES DE ENTORNO ──────────────────────────────────────
sep("8. VARIABLES DE ENTORNO (.env)")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    env_vars = {
        "GEMINI_API_KEY":      "LLM y Embeddings",
        "GEMINI_MODEL":        "Modelo activo",
        "SUPABASE_URL":        "Base de datos",
        "SUPABASE_KEY":        "Base de datos",
        "RESEND_API_KEY":      "Emails",
        "EMAIL_FROM":          "Remitente emails",
        "LANGCHAIN_TRACING_V2":"LangSmith on/off",
        "LANGCHAIN_API_KEY":   "LangSmith",
        "CHAINLIT_AUTH_SECRET":"Sesiones Chainlit",
        "TWILIO_ACCOUNT_SID":  "WhatsApp",
        "TWILIO_AUTH_TOKEN":   "WhatsApp",
        "TWILIO_WHATSAPP_FROM":"Número sandbox",
        "YOUTUBE_API_KEY":     "YouTube scraper",
    }

    for key, desc in env_vars.items():
        val = os.getenv(key, "")
        exists = bool(val)
        if exists:
            # Mostrar solo primeros/últimos chars por seguridad
            masked = val[:4] + "****" + val[-3:] if len(val) > 8 else "****"
            check(f"{key:<28} ({desc})", True, masked)
        else:
            check(f"{key:<28} ({desc})", False, "⚠️ NO CONFIGURADO")
except ImportError:
    print("  ⚠️ python-dotenv no instalado. No se pueden leer variables.")

# ── RESUMEN FINAL ─────────────────────────────────────────────
sep("9. RESUMEN")

# Contar archivos críticos faltantes
criticos = [
    ROOT / "api.py",
    ROOT / "chainlit_app.py",
    ROOT / "n8n_workflow.json",
    ROOT / "Procfile",
    ROOT / "01_codigos/tools.py",
    ROOT / "01_codigos/agent_router.py",
    ROOT / "01_codigos/database.py",
    ROOT / "01_codigos/email_service.py",
    ROOT / "01_codigos/tsne_analysis.py",
    ROOT / "data/07_estructurado/banco_info.json",
]

faltantes = [str(f.relative_to(ROOT)) for f in criticos if not f.exists()]
versiones_viejas = []

checks_version = [
    ("01_codigos/tools.py",       "ConsultaCorpusInput"),
    ("01_codigos/agent_router.py","error_occurred"),
    ("01_codigos/llm_chains.py",  "models/text-embedding-004"),
    ("01_codigos/07_chunking.py", "models/text-embedding-004"),
]
for fpath, keyword in checks_version:
    p = ROOT / fpath
    if p.exists() and not grep(p, keyword):
        versiones_viejas.append(fpath)

print()
if not faltantes and not versiones_viejas:
    print("  🎉 TODO ESTÁ EN ORDEN. El proyecto está completo.")
else:
    if faltantes:
        print(f"  ❌ ARCHIVOS FALTANTES ({len(faltantes)}):")
        for f in faltantes:
            print(f"     → {f}")
    if versiones_viejas:
        print(f"\n  ⚠️  ARCHIVOS CON VERSIÓN VIEJA ({len(versiones_viejas)}):")
        for f in versiones_viejas:
            print(f"     → {f}  (reemplazar con la versión M3)")

print(f"\n{SEPARATOR}")
print("  Copia y pega TODO este output en el chat para diagnóstico.")
print(f"{SEPARATOR}\n")
