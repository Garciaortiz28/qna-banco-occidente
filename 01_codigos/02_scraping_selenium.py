import os
import sys
import time
import re
import requests
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    URLS_FILE, PDF_URLS_FILE, SOCIAL_FILE,
    SCRAPING_DIR, PDFS_DIR, ensure_dirs
)

ensure_dirs()

DELAY_HTML = 2.5
DELAY_PDF  = 0.8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def safe_name(url, prefix=""):
    name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:140]
    return f"{prefix}{name}.txt"


def build_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def extract_page(driver):
    lines = []
    try:
        title = driver.title
        if title:
            lines.append(f"# {title.strip()}\n")
    except Exception:
        pass

    try:
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    except Exception:
        pass

    for sel in ["nav", "footer", "header", "aside",
                "[class*='cookie']", "[class*='modal']", "[class*='banner']"]:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                driver.execute_script("arguments[0].remove()", el)
        except Exception:
            pass

    for el in driver.find_elements(By.CSS_SELECTOR, "h1,h2,h3,h4,p,li,td"):
        try:
            text = el.text.strip()
            tag  = el.tag_name
            if not text or len(text) < 20:
                continue
            if tag == "h1":
                lines.append(f"\n# {text}\n")
            elif tag == "h2":
                lines.append(f"\n## {text}\n")
            elif tag == "h3":
                lines.append(f"\n### {text}\n")
            elif tag == "h4":
                lines.append(f"\n#### {text}\n")
            elif tag == "li":
                lines.append(f"- {text}")
            else:
                lines.append(text)
        except Exception:
            pass

    return "\n".join(lines)


def save_doc(url, text, prefix=""):
    path = os.path.join(SCRAPING_DIR, safe_name(url, prefix))
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n\n{text}")


def scrape_html():
    if not os.path.exists(URLS_FILE):
        print(f"  No se encontró {URLS_FILE}. Ejecuta primero el crawling.")
        return 0

    with open(URLS_FILE, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip()]

    print(f"\n  HTML: {len(urls)} páginas a procesar\n")
    driver  = build_driver()
    success = 0

    try:
        for i, url in enumerate(urls, 1):
            print(f"  [{i:>3}/{len(urls)}] {url[:70]}")
            try:
                driver.get(url)
                time.sleep(DELAY_HTML)
                text = extract_page(driver)
                if len(text) < 200:
                    print("         ↳ contenido muy corto, se omite")
                    continue
                save_doc(url, text)
                success += 1
                print(f"         ↳ {len(text):,} chars guardados")
            except Exception as e:
                print(f"         ↳ error: {str(e)[:60]}")
    finally:
        driver.quit()

    return success


def extract_pdf_text(pdf_bytes, url):
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        name   = re.sub(r"[_-]+", " ", url.split("/")[-1].replace(".pdf", "").replace("%20", " "))
        parts  = [f"# {name.strip()}\n", f"**PDF · {len(reader.pages)} páginas**\n"]

        for i, page in enumerate(reader.pages, 1):
            try:
                t = page.extract_text() or ""
                if t.strip():
                    if len(reader.pages) > 1:
                        parts.append(f"\n## Página {i}\n")
                    parts.append(t.strip())
            except Exception:
                pass

        return "\n".join(parts)
    except Exception as e:
        print(f"         ↳ error extrayendo PDF: {str(e)[:60]}")
        return ""


def scrape_pdfs():
    if not os.path.exists(PDF_URLS_FILE):
        return 0

    with open(PDF_URLS_FILE, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip()]

    if not urls:
        return 0

    print(f"\n  PDFs: {len(urls)} archivos a descargar\n")
    success = 0

    for i, url in enumerate(urls, 1):
        print(f"  [{i:>3}/{len(urls)}] {url[:70]}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"         ↳ HTTP {r.status_code}, se omite")
                continue

            pdf_bytes = r.content
            print(f"         ↳ descargado {len(pdf_bytes) / 1024:.0f} KB")

            pdf_name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:140] + ".pdf"
            with open(os.path.join(PDFS_DIR, pdf_name), "wb") as f:
                f.write(pdf_bytes)

            text = extract_pdf_text(pdf_bytes, url)
            if len(text) < 100:
                print("         ↳ texto insuficiente (probablemente PDF escaneado)")
                continue

            save_doc(url, text, prefix="pdf_")
            success += 1
            print(f"         ↳ {len(text):,} chars extraídos")
            time.sleep(DELAY_PDF)

        except Exception as e:
            print(f"         ↳ error: {str(e)[:60]}")

    return success


def build_social_doc():
    if not os.path.exists(SOCIAL_FILE):
        return False

    with open(SOCIAL_FILE, encoding="utf-8") as f:
        content = f.read()

    if "No se detectaron" in content or not content.strip():
        return False

    lines  = ["URL: https://www.bancodeoccidente.com.co/\n"]
    lines += ["# Canales Digitales y Redes Sociales — Banco de Occidente\n"]
    lines += [
        "El Banco de Occidente mantiene presencia activa en redes sociales "
        "donde los clientes pueden obtener información y atención.\n"
    ]

    current = None
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            current = line[3:].strip()
            lines.append(f"\n## {current}")
        elif line.startswith("- ") and current:
            url = line[2:].strip()
            lines.append(f"- Enlace oficial en {current}: {url}")

    path = os.path.join(SCRAPING_DIR, "redes_sociales.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return True


if __name__ == "__main__":
    print("\n=== SCRAPING — Banco de Occidente ===")
    t0 = time.time()

    html_ok   = scrape_html()
    pdf_ok    = scrape_pdfs()
    social_ok = build_social_doc()

    elapsed = time.time() - t0
    print(f"\n  HTML extraído:     {html_ok} documentos")
    print(f"  PDFs procesados:   {pdf_ok}")
    print(f"  Redes sociales:    {'incluidas' if social_ok else 'no disponible'}")
    print(f"  Tiempo total:      {elapsed:.0f}s ({elapsed/60:.1f} min)\n")
    print("Siguiente paso: python main.py --step clean\n")
