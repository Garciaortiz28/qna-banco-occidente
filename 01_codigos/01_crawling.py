import os
import sys
import time
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import URLS_FILE, PDF_URLS_FILE, SOCIAL_FILE, ensure_dirs

ensure_dirs()

BASE_URL = "https://www.bancodeoccidente.com.co/"
DOMAIN   = "bancodeoccidente.com.co"

# Se ajusta la cantidad de URLs a 500 para mayor cobertura del sitio
MAX_URLS = 500
DELAY    = 1.2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

SOCIAL_DOMAINS = {
    "facebook":  ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "twitter":   ["twitter.com", "x.com"],
    "linkedin":  ["linkedin.com"],
    "youtube":   ["youtube.com", "youtu.be"],
    "tiktok":    ["tiktok.com"],
    "whatsapp":  ["wa.me", "whatsapp.com"],
}

SKIP_EXT = [
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".rar", ".mp4", ".mp3", ".css", ".js", ".xml", ".json",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
]


def detect_social(url):
    for name, domains in SOCIAL_DOMAINS.items():
        if any(d in url.lower() for d in domains):
            return name
    return None


def is_pdf(url):
    return ".pdf" in url.lower()


def is_valid_html(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    if DOMAIN not in p.netloc:
        return False
    if any(url.lower().endswith(e) for e in SKIP_EXT):
        return False
    if "#" in url:
        return False
    return True


def get_sitemap_urls():
    candidates = [
        urljoin(BASE_URL, "sitemap.xml"),
        urljoin(BASE_URL, "sitemap_index.xml"),
    ]
    found = []
    for sitemap in candidates:
        try:
            r = requests.get(sitemap, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            ns   = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            subs = [e.text for e in root.iter(f"{ns}loc") if e.text and "sitemap" in e.text.lower()]
            if subs:
                for sub in subs[:5]:
                    try:
                        sr   = requests.get(sub, headers=HEADERS, timeout=10)
                        sroot = ET.fromstring(sr.content)
                        for loc in sroot.iter(f"{ns}loc"):
                            if loc.text:
                                found.append(loc.text)
                    except Exception:
                        pass
            for loc in root.iter(f"{ns}loc"):
                if loc.text and "sitemap" not in loc.text.lower():
                    found.append(loc.text)
            if found:
                print(f"  Sitemap: {len(found)} URLs encontradas")
                return found
        except Exception:
            pass
    return []


def crawl_bfs():
    visited = set()
    queue   = deque([BASE_URL])
    html_urls    = set()
    pdf_urls     = set()
    social_links = {}

    while queue and len(html_urls) < MAX_URLS:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if len(visited) % 25 == 0:
            print(f"  Visitadas: {len(visited)} | HTML: {len(html_urls)} | PDFs: {len(pdf_urls)}")

        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue

            ct = r.headers.get("Content-Type", "")
            if "pdf" in ct:
                pdf_urls.add(url)
                continue

            soup = BeautifulSoup(r.text, "lxml")
            for tag in soup.find_all("a", href=True):
                full = urljoin(url, tag["href"]).split("#")[0].rstrip("/")
                if not full:
                    continue
                social = detect_social(full)
                if social:
                    social_links.setdefault(social, set()).add(full)
                elif is_pdf(full):
                    pdf_urls.add(full)
                elif is_valid_html(full) and full not in visited:
                    html_urls.add(full)
                    queue.append(full)

            time.sleep(DELAY)
        except Exception as e:
            print(f"  Error en {url[:60]}: {str(e)[:50]}")

    return list(html_urls), list(pdf_urls), social_links


def get_homepage_social():
    result = {}
    try:
        r    = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup.find_all("a", href=True):
            href   = urljoin(BASE_URL, tag["href"].strip())
            social = detect_social(href)
            if social:
                result.setdefault(social, set()).add(href)
    except Exception:
        pass
    return result


def save(html_urls, pdf_urls, social_links):
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        f.writelines(u + "\n" for u in sorted(html_urls))

    with open(PDF_URLS_FILE, "w", encoding="utf-8") as f:
        f.writelines(u + "\n" for u in sorted(pdf_urls))

    with open(SOCIAL_FILE, "w", encoding="utf-8") as f:
        f.write("# Redes sociales — Banco de Occidente\n\n")
        for net, urls in sorted(social_links.items()):
            f.write(f"## {net.upper()}\n")
            for u in sorted(urls):
                f.write(f"- {u}\n")
            f.write("\n")

    print(f"\n  HTML:    {len(html_urls)} URLs  →  {URLS_FILE}")
    print(f"  PDFs:    {len(pdf_urls)}  →  {PDF_URLS_FILE}")
    print(f"  Social:  {sum(len(v) for v in social_links.values())} enlaces  →  {SOCIAL_FILE}")


if __name__ == "__main__":
    print("\n=== CRAWLING — Banco de Occidente ===\n")

    sitemap = get_sitemap_urls()

    if len(sitemap) >= 50:
        html_urls    = [u for u in sitemap if is_valid_html(u)][:MAX_URLS]
        pdf_urls     = [u for u in sitemap if is_pdf(u)]
        social_links = get_homepage_social()
    else:
        print("  Sitemap insuficiente, usando BFS...")
        html_urls, pdf_urls, social_links = crawl_bfs()
        for net, urls in get_homepage_social().items():
            social_links.setdefault(net, set()).update(urls)

    html_urls = list(set(html_urls))[:MAX_URLS]
    pdf_urls  = list(set(pdf_urls))

    save(html_urls, pdf_urls, social_links)

    print("\nSiguiente paso: python main.py --step scrape\n")
