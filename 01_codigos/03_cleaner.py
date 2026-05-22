import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SCRAPING_DIR, CLEAN_DIR, ensure_dirs

ensure_dirs()

# Patrones de ruido de UI — elementos que no aportan información
UI_NOISE = re.compile("|".join([
    r"^(inicio|home)\s*[>›/]",
    r"^(menú principal|ir al contenido|saltar al contenido)$",
    r"^(ver más|ver menos|leer más|clic aquí|click aquí)$",
    r"^(inicia sesión|cerrar sesión|login|registrarse)$",
    r"^(aceptar|cancelar|confirmar|enviar|siguiente|anterior)$",
    r"política de cookies|usamos cookies|aceptar cookies",
    r"^(síguenos|compartir|follow us)$",
    r"^(todos los derechos reservados|all rights reserved)$",
    r"^©\s*\d{4}",
    r"^(cargando|loading|espere)\.*$",
    r"^[a-záéíóú\s]+\s*[>›/]\s*[a-záéíóú\s]+\s*[>›/]",
]), re.IGNORECASE)

# Patrones de texto roto de PDFs escaneados — glifos sin mapeo y chars de control
PDF_GARBAGE = re.compile("|".join([
    r"\(cid:\d+\)",
    r"[\uFFFD\uFFFE\uFFFF]",
    r"[\u0000-\u0008\u000B\u000C\u000E-\u001F]",
    r"^\s*[/\\<>{}\[\]@#$%^&*()_+=|~`]+\s*$",
    r"^\s*\d+\s*$",
    r"(?:[A-Za-z]\s+){15,}",
]))

# Contenido bancario de alto valor — estas líneas nunca se descartan
HIGH_VALUE = re.compile(r"""
    \$[\d.,]+|
    \d+[\.,]\d+\s*%|
    (tasa|cuota|plazo|monto|mínimo|máximo)\s+\w|
    \d+\s*(meses|años|días)|
    (tarjeta|cuenta|crédito|préstamo|inversión|leasing|fiducia|cdT\b|
     hipotecario|vivienda|nómina|débito|portafolio|
     superfinanciera|fogafín|grupo aval|banco de occidente|
     banca\s+en\s+línea|portal transaccional|app\s+móvil)
""", re.IGNORECASE | re.VERBOSE)


def readability(line):
    clean = line.strip()
    if not clean:
        return 0.0
    letters = sum(1 for c in clean if c.isalpha() or c in "áéíóúñÁÉÍÓÚÑ ")
    return letters / len(clean)


def is_garbage_doc(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) < 5:
        return True, "documento muy corto"
    cid = len(re.findall(r"\(cid:\d+\)", text))
    if cid > 5:
        return True, f"{cid} glifos rotos (PDF escaneado)"
    avg = sum(readability(l) for l in lines) / len(lines)
    if avg < 0.45:
        return True, f"legibilidad global baja ({avg:.0%})"
    return False, ""


def keep_line(line):
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return True
    if HIGH_VALUE.search(s):
        return True
    if PDF_GARBAGE.search(s):
        return False
    if UI_NOISE.search(s):
        return False
    if readability(s) < 0.60 and len(s) > 15:
        return False
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{8,}", s, re.IGNORECASE):
        return False
    if re.search(r"[A-Z]{25,}", s):
        return False
    return len(s) >= 18


def clean_doc(raw):
    seen  = set()
    lines = []
    for line in raw.split("\n"):
        if not keep_line(line):
            continue
        key = line.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text)


def run():
    files = [
    os.path.join(root, f)
    for root, _, filenames in os.walk(SCRAPING_DIR)
    for f in filenames
    if f.endswith(".txt") and not f.startswith("_")
]
    print(f"\n=== CLEANER — {len(files)} documentos ===\n")

    kept     = 0
    garbage  = 0
    too_short = 0

    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        content = re.sub(r"^URL:.*?\n\n", "", raw, count=1, flags=re.DOTALL).strip()

        bad, reason = is_garbage_doc(content)
        if bad:
            garbage += 1
            print(f"  [{i:>3}] ✗ {fname[:55]:<55} ({reason})")
            continue

        cleaned = clean_doc(raw)

        if len(cleaned.strip()) < 200:
            too_short += 1
            print(f"  [{i:>3}] ⚠ {fname[:55]:<55} (muy corto tras limpieza)")
            continue

        out = os.path.join(CLEAN_DIR, fname)
        with open(out, "w", encoding="utf-8") as f:
            f.write(cleaned)

        kept += 1
        raw_l   = len([l for l in raw.split("\n") if l.strip()])
        clean_l = len([l for l in cleaned.split("\n") if l.strip()])
        pct     = clean_l / max(raw_l, 1) * 100
        print(f"  [{i:>3}] ✓ {fname[:55]:<55} {clean_l:>4} líneas ({pct:.0f}%)")

    print(f"\n  Conservados:  {kept}")
    print(f"  Basura PDF:   {garbage}")
    print(f"  Muy cortos:   {too_short}")
    print("\nSiguiente paso: python main.py --step md\n")


if __name__ == "__main__":
    run()
