import sys
import os
import argparse
import subprocess

CODIGOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "01_codigos")
sys.path.insert(0, CODIGOS_DIR)


def run_step(script_name: str, description: str):
    script_path = os.path.join(CODIGOS_DIR, script_name)
    print(f"\n{'═' * 65}")
    print(f"▶  {description}")
    print(f"{'═' * 65}\n")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        print(f"\n❌ Error en {script_name} (código {result.returncode})")
        sys.exit(result.returncode)
    print(f"\n✅ {description} completado.")


def run_app():
    app_path = os.path.join(CODIGOS_DIR, "app.py")
    print(f"\n{'═' * 65}")
    print("▶  Lanzando interfaz Streamlit...")
    print(f"{'═' * 65}\n")
    subprocess.run(["streamlit", "run", app_path])


STEPS = {
    "reset":   ("00_reset.py",              "Limpieza completa del proyecto"),
    "crawl":   ("01_crawling.py",            "Crawling de URLs del banco"),
    "scrape":  ("02_scraping_selenium.py",   "Scraping HTML + descarga de PDFs"),
    "clean":   ("03_cleaner.py",            "Limpieza y filtrado del corpus"),
    "md":      ("04_markdown_builder.py",    "Conversión a Markdown estructurado"),
    "corpus":  ("05_corpus_master.py",       "Construcción del corpus maestro"),
    "youtube": ("06_youtube_scraper.py",     "Scraping del canal YouTube del banco"),
    "chunks":  ("07_chunking.py",            "Chunking semántico + ChromaDB embeddings"),
}

PIPELINE_BASE = ["crawl", "scrape", "clean", "md", "corpus", "chunks"]
PIPELINE_FULL = ["crawl", "scrape", "youtube", "clean", "md", "corpus", "chunks"]


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Q&A + Agente · Banco de Occidente",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--step",
        choices=list(STEPS.keys()),
        help="\n".join(f"  {k:<10} → {v[1]}" for k, v in STEPS.items()),
    )
    group.add_argument(
        "--pipeline",
        action="store_true",
        help="Pipeline base: crawl → scrape → clean → md → corpus → chunks",
    )
    group.add_argument(
        "--pipeline-full",
        action="store_true",
        help="Pipeline completo (con YouTube): crawl → scrape → youtube → clean → md → corpus → chunks",
    )
    group.add_argument(
        "--app",
        action="store_true",
        help="Lanzar la interfaz Streamlit",
    )

    args = parser.parse_args()

    if args.step:
        script, description = STEPS[args.step]
        run_step(script, description)

    elif args.pipeline:
        print("\n🚀 PIPELINE BASE — Banco de Occidente")
        for step in PIPELINE_BASE:
            run_step(*STEPS[step])
        print("\n🎉 Pipeline completado. Lanza la app con: python main.py --app\n")

    elif getattr(args, "pipeline_full", False):
        print("\n🚀 PIPELINE COMPLETO — Banco de Occidente")
        for step in PIPELINE_FULL:
            run_step(*STEPS[step])
        print("\n🎉 Pipeline completo. Lanza la app con: python main.py --app\n")

    elif args.app:
        run_app()


if __name__ == "__main__":
    main()
