"""
llm_chains.py — Motor RAG v4.1
Banco de Occidente — Módulo 3

Cambios v4.1:
- Eliminado import ChatGoogleGenerativeAI (no usado, causaba FutureWarning)
- Corregida indentación de HuggingFaceEmbeddings
- Agregado normalize_embeddings=True para mejor similitud coseno
- Logging estructurado
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
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.10"))


@lru_cache(maxsize=1)
def _load_vector_store() -> Chroma:
    """Carga ChromaDB una sola vez (singleton via lru_cache)."""
    embedding_fn = HuggingFaceEmbeddings(
        model_name    = EMBEDDING_MODEL,
        model_kwargs  = {"device": "cpu"},
        encode_kwargs = {"normalize_embeddings": True},
    )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    client.get_or_create_collection(CHROMA_COLLECTION)
    return Chroma(
        client             = client,
        collection_name    = CHROMA_COLLECTION,
        embedding_function = embedding_fn,
    )


def _retrieve_context(query: str, k: int = 5) -> tuple:
    """Recupera los k chunks más relevantes del corpus."""
    store = _load_vector_store()
    try:
        results = store.similarity_search_with_relevance_scores(query, k=k)
    except Exception as e:
        print(f"[rag] Error en búsqueda: {e}")
        return "", []

    relevant = [(doc, score) for doc, score in results if score >= SIMILARITY_THRESHOLD]

    if not relevant:
        if results:
            scores = [f"{s:.3f}" for _, s in results[:3]]
            print(f"[rag] Sin resultados sobre umbral {SIMILARITY_THRESHOLD}. Top scores: {scores}")
        return "", []

    print(f"[rag] {len(relevant)} chunks relevantes (top score: {relevant[0][1]:.3f})")
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
