"""
llm_chains.py — Motor RAG v4.2
Banco de Occidente — Módulo 3

Cambios v4.2:
- Logging exhaustivo en _load_vector_store y _retrieve_context para
  diagnóstico remoto en Railway (modelo, ruta, scores, threshold)
- Diagnóstico al importar el módulo (modelo + ruta ChromaDB)

Cambios v4.1:
- Eliminado import ChatGoogleGenerativeAI (no usado, causaba FutureWarning)
- Corregida indentación de HuggingFaceEmbeddings
- Agregado normalize_embeddings=True para mejor similitud coseno
"""

import os
import sys
from functools import lru_cache
from dotenv import load_dotenv

import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CHROMA_DIR, CHROMA_COLLECTION

load_dotenv()

# ── Configuración ─────────────────────────────────────────
EMBEDDING_MODEL      = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.10"))

# ── Diagnóstico al importar (visible en logs de Railway) ──
print(f"[rag] EMBEDDING_MODEL={EMBEDDING_MODEL}")
print(f"[rag] SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD}")
print(f"[rag] CHROMA_DIR={CHROMA_DIR}")
print(f"[rag] CHROMA_COLLECTION={CHROMA_COLLECTION}")


@lru_cache(maxsize=1)
def _load_vector_store() -> Chroma:
    """Carga ChromaDB una sola vez (singleton via lru_cache)."""
    print(f"[rag] Cargando modelo de embeddings: {EMBEDDING_MODEL}")
    try:
        embedding_fn = HuggingFaceEmbeddings(
            model_name    = EMBEDDING_MODEL,
            model_kwargs  = {"device": "cpu"},
            encode_kwargs = {"normalize_embeddings": True},
        )
        print(f"[rag] Modelo de embeddings cargado OK")
    except Exception as e:
        print(f"[rag] ERROR cargando modelo de embeddings: {e}")
        raise

    print(f"[rag] Conectando a ChromaDB en: {CHROMA_DIR}")
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col    = client.get_or_create_collection(CHROMA_COLLECTION)
        total  = col.count()
        print(f"[rag] ChromaDB OK — coleccion '{CHROMA_COLLECTION}' con {total} chunks")
        if total == 0:
            print(f"[rag] ADVERTENCIA: coleccion vacia — el RAG no retornara resultados")
    except Exception as e:
        print(f"[rag] ERROR conectando a ChromaDB: {e}")
        raise

    store = Chroma(
        client             = client,
        collection_name    = CHROMA_COLLECTION,
        embedding_function = embedding_fn,
    )
    print(f"[rag] Vector store listo")
    return store


def _retrieve_context(query: str, k: int = 5) -> tuple:
    """Recupera los k chunks más relevantes del corpus."""
    print(f"[rag] Buscando: '{query[:60]}'")
    print(f"[rag] Modelo={EMBEDDING_MODEL} | Threshold={SIMILARITY_THRESHOLD} | k={k}")

    store = _load_vector_store()

    try:
        results = store.similarity_search_with_relevance_scores(query, k=k)
        print(f"[rag] Resultados brutos: {len(results)}")
        for doc, score in results[:3]:
            print(f"[rag]   score={score:.3f} | '{doc.page_content[:70].strip()}'")
    except Exception as e:
        print(f"[rag] ERROR en similarity_search: {e}")
        return "", []

    relevant = [(doc, score) for doc, score in results if score >= SIMILARITY_THRESHOLD]
    print(f"[rag] Relevantes sobre threshold {SIMILARITY_THRESHOLD}: {len(relevant)}/{len(results)}")

    if not relevant:
        print(f"[rag] NINGUNO supera el threshold — retornando REFUSAL_MSG")
        return "", []

    print(f"[rag] Top score: {relevant[0][1]:.3f} | Retornando {len(relevant)} chunks")
    docs_text = "\n\n---\n\n".join(doc.page_content for doc, _ in relevant)
    return docs_text, [doc for doc, _ in relevant]


_QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Eres el Asistente Virtual del Banco de Occidente.

INSTRUCCIONES:
1. Responde ÚNICAMENTE usando el CONTEXTO proporcionado.
2. Si el contexto no contiene la respuesta, di que no tienes esa información.
3. NUNCA inventes tasas, montos, fechas ni datos bancarios.
4. Responde en español formal y cálido, primera persona del banco.
5. Máximo 4 párrafos.

CONTEXTO:
{context}"""),
    ("human", "{question}"),
])

_REFUSAL_MSG = (
    "No cuento con información específica sobre ese tema en este momento. "
    "Para atención personalizada, llama al 01 8000 514 652 o visita "
    "www.bancodeoccidente.com.co"
)


def ask_question(query: str, temperature: float = 0.1) -> str:
    """
    Recupera contexto del corpus. El agente principal sintetiza la respuesta.
    """
    context, docs = _retrieve_context(query)
    if not context:
        return _REFUSAL_MSG
    return f"INFORMACIÓN ENCONTRADA EN EL CORPUS:\n\n{context}"


def is_banking_query(query: str) -> bool:
    """Verifica si la consulta es sobre temas bancarios."""
    _, docs = _retrieve_context(query, k=1)
    return len(docs) > 0
