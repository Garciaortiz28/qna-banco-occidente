import os
import sys
import re
import hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import MARKDOWN_DIR, CORPUS_FILE, ensure_dirs

ensure_dirs()

CATEGORIES = {
    "institucional": [
        "quiénes somos", "historia", "misión", "visión", "valores",
        "gobierno corporativo", "sostenibilidad", "responsabilidad",
        "grupo aval", "informe", "junta directiva", "accionistas",
    ],
    "cuentas": [
        "cuenta de ahorro", "cuenta corriente", "cuenta nómina",
        "cuenta de depósito", "apertura de cuenta", "saldo",
        "extracto", "consignación",
    ],
    "tarjetas": [
        "tarjeta de crédito", "tarjeta débito", "tarjeta prepago",
        "visa", "mastercard", "cupo", "cuota",
    ],
    "creditos": [
        "crédito", "préstamo", "financiamiento", "libre inversión",
        "crédito hipotecario", "crédito vehicular", "crédito de vehículo",
        "leasing", "libranza", "cartera",
    ],
    "inversion": [
        "inversión", "cdt", "certificado de depósito", "fondos",
        "portafolio", "rentabilidad", "fiducia", "mercado de capitales",
        "banca de inversión",
    ],
    "empresarial": [
        "empresas", "pyme", "corporativo", "comercio exterior",
        "nómina empresarial", "factoring", "confirming",
        "tesorería", "cash management",
    ],
    "seguros": [
        "seguro", "póliza", "protección", "vida", "cobertura",
        "asistencia",
    ],
    "digital": [
        "banca en línea", "portal transaccional", "app", "aplicación",
        "servicios digitales", "transfer", "pse", "qr",
        "pagos electrónicos",
    ],
    "atencion": [
        "atención al cliente", "servicio al cliente", "sucursal",
        "agencia", "cajero", "horario", "teléfono", "contacto",
        "línea de atención", "redes sociales",
    ],
    "legal": [
        "términos", "condiciones", "reglamento", "superfinanciera",
        "fogafín", "normativa", "política", "habeas data",
    ],
}


def categorize(text):
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score:
            scores[cat] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)


def shingling(text, k=4):
    words = text.lower().split()
    shingles = set()
    for i in range(len(words) - k + 1):
        shingles.add(tuple(words[i:i+k]))
    return shingles


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def run():
    files = [f for f in os.listdir(MARKDOWN_DIR) if f.endswith(".md")]
    print(f"\n=== CORPUS MASTER — {len(files)} documentos ===\n")

    buckets = {cat: [] for cat in CATEGORIES}
    buckets["general"] = []

    seen_shingles = []
    dup_count     = 0

    for fname in files:
        path = os.path.join(MARKDOWN_DIR, fname)
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()

        if len(text) < 150:
            continue

        shingles = shingling(text)
        is_dup = any(jaccard(shingles, s) > 0.85 for s in seen_shingles)
        if is_dup:
            dup_count += 1
            continue
        seen_shingles.append(shingles)

        cat = categorize(text)
        buckets[cat].append((fname, text))

    lines_out = []
    lines_out.append("# Corpus Maestro — Banco de Occidente")
    lines_out.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines_out.append(f"URL base: https://www.bancodeoccidente.com.co/\n")

    total_docs = 0
    for cat, docs in buckets.items():
        if not docs:
            continue
        label = cat.replace("_", " ").title()
        lines_out.append(f"\n{'='*60}")
        lines_out.append(f"# CATEGORÍA: {label.upper()}  ({len(docs)} documentos)")
        lines_out.append(f"{'='*60}\n")
        for fname, text in docs:
            lines_out.append(text)
            lines_out.append(f"\n{'─'*40}\n")
            total_docs += 1

    corpus = "\n".join(lines_out)
    with open(CORPUS_FILE, "w", encoding="utf-8") as f:
        f.write(corpus)

    size_kb = os.path.getsize(CORPUS_FILE) / 1024
    print(f"  Documentos incluidos:   {total_docs}")
    print(f"  Duplicados descartados: {dup_count}")
    print(f"  Tamaño del corpus:      {size_kb:.0f} KB")
    print(f"  Guardado en:            {CORPUS_FILE}\n")

    print("  Distribución por categoría:")
    for cat, docs in buckets.items():
        if docs:
            print(f"    {cat:<20} {len(docs)} docs")

    print("\nSiguiente paso: python main.py --app\n")


if __name__ == "__main__":
    run()
