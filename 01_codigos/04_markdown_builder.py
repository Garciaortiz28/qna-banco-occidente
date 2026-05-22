import os
import sys
import re
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CLEAN_DIR, MARKDOWN_DIR, ensure_dirs

ensure_dirs()

# Boilerplate que se repite en muchas páginas — se deduplica a nivel global
BOILERPLATE_PATTERNS = re.compile("|".join([
    r"^(conoce|descubre|entérate|consulta) (más|nuestros|nuestras)",
    r"^(solicita|pide) (tu|el|la|un|una)",
    r"^(comunícate|contáctanos|escríbenos)",
    r"banco de occidente\s*[-–]\s*(todo|ser|hacer|transformar)",
    r"^(nuestros productos|nuestros servicios|lo que ofrecemos)$",
    r"^(términos y condiciones|aviso legal|política de privacidad)$",
    r"^(copyright|©)\s*\d{4}",
]), re.IGNORECASE)

global_seen = set()


def fingerprint(text):
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def is_boilerplate(line):
    return bool(BOILERPLATE_PATTERNS.search(line.strip()))


def tag_to_heading(line):
    line = line.strip()
    if re.match(r"^#{1,4}\s", line):
        return line
    if re.match(r"^[A-ZÁÉÍÓÚ][^.!?]{5,60}$", line) and not line.endswith((",", ";")):
        return f"## {line}"
    return line


def build_markdown(raw_text, source_url=""):
    lines  = raw_text.split("\n")
    output = []

    if source_url:
        output.append(f"<!-- fuente: {source_url} -->")

    for line in lines:
        line = line.rstrip()

        if not line.strip():
            output.append("")
            continue

        if is_boilerplate(line):
            continue

        fp = fingerprint(line)
        if fp in global_seen:
            continue
        global_seen.add(fp)

        output.append(tag_to_heading(line))

    text = "\n".join(output)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_url(raw):
    m = re.match(r"URL:\s*(.+)", raw)
    return m.group(1).strip() if m else ""


def run():
    files = [f for f in os.listdir(CLEAN_DIR) if f.endswith(".txt")]
    print(f"\n=== MARKDOWN BUILDER — {len(files)} documentos ===\n")

    ok   = 0
    skip = 0

    for i, fname in enumerate(files, 1):
        path = os.path.join(CLEAN_DIR, fname)
        with open(path, encoding="utf-8") as f:
            raw = f.read()

        url     = extract_url(raw)
        content = re.sub(r"^URL:.*?\n\n", "", raw, count=1, flags=re.DOTALL)
        md      = build_markdown(content, source_url=url)

        if len(md.strip()) < 100:
            skip += 1
            print(f"  [{i:>3}] ⚠ {fname[:55]:<55} (vacío tras deduplicación)")
            continue

        out = os.path.join(MARKDOWN_DIR, fname.replace(".txt", ".md"))
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)

        ok += 1
        lines = len([l for l in md.split("\n") if l.strip()])
        print(f"  [{i:>3}] ✓ {fname[:55]:<55} {lines:>4} líneas")

    print(f"\n  Generados: {ok}")
    print(f"  Omitidos:  {skip}")
    print(f"  Frases deduplicadas globalmente: {len(global_seen)}")
    print("\nSiguiente paso: python main.py --step corpus\n")


if __name__ == "__main__":
    run()
