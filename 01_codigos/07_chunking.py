"""
07_chunking.py — Pipeline de chunking e indexación con Google Embeddings
Genera embeddings con Google text-embedding-004 y los indexa en ChromaDB.

IMPORTANTE: Ejecutar esto borra y recrea el índice completo.
Comando: python main.py --step chunks
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    CORPUS_MASTER, CHROMA_DIR, CHROMA_COLLECTION,
    MARKDOWN_DIR, YOUTUBE_DIR
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Configuración de embeddings ─────────────────────────
# Google text-embedding-004: 768 dim, estado del arte
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


# ── Configuración de chunking ───────────────────────────
CHUNK_SIZE    = 700
CHUNK_OVERLAP = 120
BATCH_SIZE    = 20   # Google embeddings API: batches pequeños para respetar quota

print(f"""
╔══════════════════════════════════════════════════════╗
║  CHUNKING + INDEXACIÓN — Google text-embedding-004  ║
║  Modelo: {EMBEDDING_MODEL:<40} ║
║  Chunk size: {CHUNK_SIZE}  │  Overlap: {CHUNK_OVERLAP}  │  Batch: {BATCH_SIZE}          ║
╚══════════════════════════════════════════════════════╝
""")


def _build_embedding_fn():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"}
    )


def _collect_documents() -> list[dict]:
    """
    Recolecta todos los documentos del corpus con sus metadatos.
    Retorna lista de {'text': ..., 'metadata': {...}}
    """
    documents = []

    # ── Corpus HTML/PDF (corpus_master.md) ─────────────
    if Path(CORPUS_MASTER).exists():
        with open(CORPUS_MASTER, "r", encoding="utf-8") as f:
            content = f.read()

        # Dividir por documentos (separados por "---")
        sections = content.split("\n---\n")
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # Detectar tipo de fuente y categoría desde headers
            lines     = section.split("\n")
            categoria = "general"
            tipo      = "html"

            for line in lines[:5]:
                if "## " in line:
                    line_lower = line.lower()
                    for cat in ["credito", "tarjeta", "cuenta", "seguro",
                                "inversion", "servicio", "empresa", "digital"]:
                        if cat in line_lower:
                            categoria = cat + "s"
                            break
                if ".pdf" in line.lower():
                    tipo = "pdf"

            documents.append({
                "text":     section,
                "metadata": {
                    "tipo_fuente": tipo,
                    "categoria":   categoria,
                    "doc_index":   i,
                }
            })

        print(f"[corpus] {len(documents)} documentos del corpus maestro")

    # ── Transcripciones de YouTube ──────────────────────
    yt_dir = Path(YOUTUBE_DIR) if hasattr(sys.modules[__name__], 'YOUTUBE_DIR') else None
    if yt_dir and yt_dir.exists():
        for yt_file in yt_dir.glob("*.md"):
            try:
                with open(yt_file, "r", encoding="utf-8") as f:
                    yt_content = f.read()
                documents.append({
                    "text": yt_content,
                    "metadata": {
                        "tipo_fuente": "youtube",
                        "categoria":   "general",
                        "archivo":     yt_file.name,
                    }
                })
            except Exception:
                pass

        yt_count = sum(1 for d in documents if d["metadata"]["tipo_fuente"] == "youtube")
        print(f"[youtube] {yt_count} documentos de YouTube")

    return documents


def _chunk_documents(documents: list[dict]) -> tuple[list[str], list[dict]]:
    """
    Divide los documentos en chunks con el splitter configurado.
    Retorna (textos, metadatos).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["## ", "### ", "\n\n", "\n", ". ", " "],
    )

    all_texts   = []
    all_meta    = []
    chunk_count = 0

    for doc in documents:
        chunks = splitter.split_text(doc["text"])
        for i, chunk in enumerate(chunks):
            chunk_count += 1
            all_texts.append(chunk)
            all_meta.append({
                **doc["metadata"],
                "chunk_id": f"chunk_{chunk_count:05d}",
                "sub_index": i,
            })

    print(f"[chunking] {chunk_count} chunks generados")
    return all_texts, all_meta


def _index_to_chromadb(texts: list[str], metadatas: list[dict]) -> int:
    """
    Indexa los chunks en ChromaDB usando Google Embeddings.
    Resetea la colección antes de indexar.
    Retorna el número de chunks indexados.
    """
    embedding_fn = _build_embedding_fn()

    # Resetear ChromaDB
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Eliminar colección si existe
    try:
        client.delete_collection(CHROMA_COLLECTION)
        print(f"[chroma] Colección '{CHROMA_COLLECTION}' eliminada (reindexando)")
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    total     = len(texts)
    indexed   = 0
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"[chroma] Indexando {total} chunks en {n_batches} batches...")

    for b in range(n_batches):
        start = b * BATCH_SIZE
        end   = min(start + BATCH_SIZE, total)

        batch_texts = texts[start:end]
        batch_meta  = metadatas[start:end]
        batch_ids   = [m["chunk_id"] for m in batch_meta]

        # Generar embeddings con Google
        try:
            embeddings = embedding_fn.embed_documents(batch_texts)
        except Exception as e:
            print(f"[chroma] Error en batch {b+1}: {e}")
            # Esperar y reintentar en caso de rate limit
            time.sleep(5)
            try:
                embeddings = embedding_fn.embed_documents(batch_texts)
            except Exception as e2:
                print(f"[chroma] Batch {b+1} fallido permanentemente: {e2}")
                continue

        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=embeddings,
            metadatas=batch_meta,
        )

        indexed += len(batch_texts)
        pct      = (indexed / total) * 100

        print(f"  Batch {b+1:3d}/{n_batches} | {indexed:5d}/{total} chunks | {pct:5.1f}%")

        # Respetar quota de la API (60 RPM para embeddings)
        if b < n_batches - 1:
            time.sleep(0.5)

    return indexed


def run_chunking_pipeline() -> int:
    """
    Pipeline completo de chunking e indexación.
    Retorna el número de chunks indexados.
    """
    t0 = time.time()

    print("\n[1/3] Recolectando documentos...")
    documents = _collect_documents()

    if not documents:
        print("ERROR: No se encontraron documentos. Ejecuta el pipeline de scraping primero.")
        return 0

    print("\n[2/3] Dividiendo en chunks...")
    texts, metadatas = _chunk_documents(documents)

    print("\n[3/3] Indexando en ChromaDB con Google text-embedding-004...")
    indexed = _index_to_chromadb(texts, metadatas)

    elapsed = time.time() - t0
    print(f"""
╔══════════════════════════════════════════════════════╗
║  ✅ INDEXACIÓN COMPLETADA                            ║
║  Chunks indexados: {indexed:<34} ║
║  Tiempo total: {elapsed/60:.1f} minutos{'':<35} ║
╚══════════════════════════════════════════════════════╝
""")
    return indexed


if __name__ == "__main__":
    run_chunking_pipeline()
