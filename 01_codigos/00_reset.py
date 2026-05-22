import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    URLS_FILE, PDF_URLS_FILE, SOCIAL_FILE, CORPUS_FILE,
    SCRAPING_DIR, PDFS_DIR, CLEAN_DIR, MARKDOWN_DIR, CORPUS_DIR
)

FILES = [URLS_FILE, PDF_URLS_FILE, SOCIAL_FILE, CORPUS_FILE]
DIRS  = [SCRAPING_DIR, PDFS_DIR, CLEAN_DIR, MARKDOWN_DIR]


def size_mb(path):
    if not os.path.exists(path):
        return 0.0
    if os.path.isfile(path):
        return os.path.getsize(path) / 1_048_576
    total = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, fs in os.walk(path)
        for f in fs
    )
    return total / 1_048_576


def run(auto=False):
    print("\n=== RESET — Sistema Q&A Banco de Occidente ===\n")

    total_mb  = sum(size_mb(p) for p in FILES + DIRS if os.path.exists(p))
    hay_algo  = any(os.path.exists(p) for p in FILES + DIRS)

    if not hay_algo:
        print("El proyecto ya está limpio, nada que borrar.\n")
        return

    for p in FILES:
        if os.path.exists(p):
            print(f"  {os.path.basename(p):<40} {size_mb(p):.2f} MB")
    for d in DIRS:
        if os.path.exists(d):
            n = sum(len(fs) for _, _, fs in os.walk(d))
            print(f"  {os.path.relpath(d):<40} {size_mb(d):.2f} MB  ({n} archivos)")

    print(f"\n  Total a liberar: {total_mb:.2f} MB\n")

    if not auto:
        resp = input("¿Confirmas? Escribe SI para continuar: ")
        if resp.strip().upper() != "SI":
            print("Cancelado.\n")
            return

    for p in FILES:
        if os.path.exists(p):
            os.remove(p)
            print(f"  Borrado: {os.path.basename(p)}")

    for d in DIRS:
        if os.path.exists(d):
            for entry in os.listdir(d):
                full = os.path.join(d, entry)
                if os.path.isfile(full):
                    os.remove(full)
                else:
                    shutil.rmtree(full)
            print(f"  Limpiado: {os.path.relpath(d)}/")

    pycache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__")
    if os.path.exists(pycache):
        shutil.rmtree(pycache)

    print(f"\n  {total_mb:.2f} MB liberados.\n")
    print("Siguiente paso: python main.py --step crawl\n")


if __name__ == "__main__":
    run(auto="--auto" in sys.argv)
