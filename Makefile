# ════════════════════════════════════════════════════════════════
# Makefile — Sistema RAG Banco de Occidente
# Maestría en IA y CD · Universidad Autónoma de Occidente
#
# USO:
#   make setup      → instalar dependencias con UV
#   make crawl      → descubrir URLs
#   make scrape     → extraer contenido
#   make clean      → limpiar corpus
#   make corpus     → construir base de conocimiento
#   make pipeline   → ejecutar todo el pipeline
#   make app        → lanzar Streamlit
#   make reset      → limpiar todos los datos generados
#   make status     → ver estado del proyecto
# ════════════════════════════════════════════════════════════════

PYTHON     = .venv/Scripts/python
STREAMLIT  = .venv/Scripts/streamlit
CODIGOS    = 01_codigos

.DEFAULT_GOAL := help

# ── Ayuda ────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo.
	@echo  ╔═══════════════════════════════════════════════════╗
	@echo  ║   Sistema Q&A · Banco de Occidente · UAO 2026    ║
	@echo  ╚═══════════════════════════════════════════════════╝
	@echo.
	@echo  Comandos disponibles:
	@echo.
	@echo    make setup      Instalar entorno y dependencias con UV
	@echo    make crawl      Crawling de URLs del sitio del banco
	@echo    make scrape     Scraping HTML + descarga de PDFs
	@echo    make clean      Limpieza inteligente del corpus
	@echo    make corpus     Construir corpus maestro final
	@echo    make pipeline   Pipeline completo (crawl→scrape→clean→corpus)
	@echo    make app        Lanzar interfaz Streamlit
	@echo    make reset      Eliminar todos los datos generados
	@echo    make status     Ver estado del proyecto
	@echo    make lint       Verificar calidad del código
	@echo.

# ── Setup ────────────────────────────────────────────────────────
.PHONY: setup
setup:
	@echo [1/3] Creando entorno virtual con UV...
	uv venv
	@echo [2/3] Instalando dependencias...
	uv pip install -r requirements.txt
	@echo [3/3] Listo. Activa el entorno con: .venv\Scripts\activate
	@echo.
	@echo Verifica la instalacion con: make status

# ── Pipeline individual ──────────────────────────────────────────
.PHONY: crawl
crawl:
	$(PYTHON) main.py --step crawl

.PHONY: scrape
scrape:
	$(PYTHON) main.py --step scrape

.PHONY: clean-corpus
clean-corpus:
	$(PYTHON) main.py --step clean

.PHONY: md
md:
	$(PYTHON) main.py --step md

.PHONY: corpus
corpus:
	$(PYTHON) main.py --step corpus

# ── Pipeline completo ────────────────────────────────────────────
.PHONY: pipeline
pipeline:
	$(PYTHON) main.py --pipeline

# ── Aplicación ──────────────────────────────────────────────────
.PHONY: app
app:
	$(STREAMLIT) run $(CODIGOS)/app.py

# ── Reset ────────────────────────────────────────────────────────
.PHONY: reset
reset:
	$(PYTHON) main.py --step reset

# ── Estado del proyecto ──────────────────────────────────────────
.PHONY: status
status:
	@echo.
	@echo === ESTADO DEL PROYECTO ===
	@echo.
	@echo [Python / UV]
	@$(PYTHON) --version
	@echo.
	@echo [Dependencias principales]
	@$(PYTHON) -c "import streamlit; print('streamlit', streamlit.__version__)"
	@$(PYTHON) -c "import langchain; print('langchain', langchain.__version__)"
	@$(PYTHON) -c "import sklearn; print('scikit-learn', sklearn.__version__)"
	@echo.
	@echo [API Key]
	@$(PYTHON) -c "from dotenv import load_dotenv; load_dotenv(); import os; k=os.getenv('GEMINI_API_KEY'); print('GEMINI_API_KEY:', 'OK' if k else 'NO DEFINIDA')"
	@echo.
	@echo [Datos generados]
	@$(PYTHON) -c "import os; dirs=[('01_urls','URLs'),('02_scraping','Scraping'),('03_pdfs','PDFs'),('04_clean','Clean'),('05_markdown','Markdown'),('06_corpus','Corpus')]; [print(f'  {d[1]:<12}: {len(os.listdir(os.path.join(\"data\",d[0]))) if os.path.exists(os.path.join(\"data\",d[0])) else 0} archivos') for d in dirs]"
	@echo.

# ── Calidad de código ────────────────────────────────────────────
.PHONY: lint
lint:
	uv run ruff check $(CODIGOS)/

# ── Limpieza de cache Python ─────────────────────────────────────
.PHONY: pyclean
pyclean:
	@if exist $(CODIGOS)\__pycache__ rmdir /s /q $(CODIGOS)\__pycache__
	@if exist __pycache__ rmdir /s /q __pycache__
	@echo Cache de Python limpiado.
