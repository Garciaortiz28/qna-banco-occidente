import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

URLS_DIR          = os.path.join(ROOT, "data", "01_urls")
SCRAPING_DIR      = os.path.join(ROOT, "data", "02_scraping")
PDFS_DIR          = os.path.join(ROOT, "data", "03_pdfs")
CLEAN_DIR         = os.path.join(ROOT, "data", "04_clean")
MARKDOWN_DIR      = os.path.join(ROOT, "data", "05_markdown")
CORPUS_DIR        = os.path.join(ROOT, "data", "06_corpus")
ESTRUCTURADO_DIR  = os.path.join(ROOT, "data", "07_estructurado")
CHROMA_DIR        = os.path.join(ROOT, "data", "08_chroma")

URLS_FILE         = os.path.join(URLS_DIR,         "urls.txt")
PDF_URLS_FILE     = os.path.join(URLS_DIR,         "pdf_urls.txt")
SOCIAL_FILE       = os.path.join(URLS_DIR,         "social_links.txt")
CORPUS_FILE       = os.path.join(CORPUS_DIR,       "corpus_master.md")
BANCO_INFO_JSON   = os.path.join(ESTRUCTURADO_DIR, "banco_info.json")

CHROMA_COLLECTION = "banco_occidente"

# Aliases y rutas adicionales para M3
CORPUS_MASTER     = CORPUS_FILE
YOUTUBE_DIR       = os.path.join(MARKDOWN_DIR, "youtube")
MEMORIA_DIR       = os.path.join(ROOT, "data", "memoria")
MEMORIA_PATH      = os.path.join(MEMORIA_DIR, "sesion.json")

def ensure_dirs():
    for d in [URLS_DIR, SCRAPING_DIR, PDFS_DIR, CLEAN_DIR, MARKDOWN_DIR,
              CORPUS_DIR, ESTRUCTURADO_DIR, CHROMA_DIR, MEMORIA_DIR]:
        os.makedirs(d, exist_ok=True)