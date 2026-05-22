"""
tsne_analysis.py — Análisis de conversaciones con t-SNE
Módulo 3 (Componente opcional pero de alto impacto).

Convierte cada conversación en un embedding, aplica t-SNE para
reducir a 2D y visualiza clusters de temas con Plotly.

Ejecutar: python 01_codigos/tsne_analysis.py
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

# ── Verificar dependencias ──────────────────────────────
try:
    from sklearn.manifold import TSNE
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
except ImportError:
    print("ERROR: pip install scikit-learn")
    sys.exit(1)

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.offline import plot
except ImportError:
    print("ERROR: pip install plotly")
    sys.exit(1)

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL = "models/text-embedding-004"
except ImportError:
    print("ERROR: pip install langchain-google-genai")
    sys.exit(1)


# ══════════════════════════════════════════════════════════
# CARGA DE CONVERSACIONES DESDE SUPABASE
# ══════════════════════════════════════════════════════════

def load_all_conversations() -> list[dict]:
    """
    Carga todas las conversaciones de Supabase.
    Retorna: lista de {session_id, texto_completo, n_turnos}
    """
    try:
        from database import get_client
        db = get_client()

        result = db.table("conversaciones")\
            .select("email_usuario, mensajes")\
            .execute()

        conversations = []
        for row in result.data:
            mensajes = row.get("mensajes", [])
            if not mensajes:
                continue

            # Concatenar toda la conversación como texto
            texto = " ".join(
                m.get("content", "")
                for m in mensajes
                if m.get("content")
            )

            if len(texto) > 20:  # Ignorar conversaciones muy cortas
                conversations.append({
                    "session_id":  row["email_usuario"],
                    "texto":       texto[:3000],  # Limitar para embeddings
                    "n_turnos":    len(mensajes) // 2,
                    "mensajes":    mensajes,
                })

        print(f"[tsne] {len(conversations)} conversaciones cargadas de Supabase")
        return conversations

    except Exception as e:
        print(f"[tsne] Error cargando de Supabase: {e}")
        print("[tsne] Usando datos de ejemplo para demostración...")
        return _generate_sample_data()


def _generate_sample_data() -> list[dict]:
    """Datos de ejemplo si no hay conexión a Supabase."""
    samples = [
        {"texto": "tarjeta crédito occiflex beneficios descuentos compras", "tema": "Tarjetas"},
        {"texto": "crédito hipotecario casa vivienda requisitos documentos", "tema": "Créditos"},
        {"texto": "teléfono atención cliente número llamar fraude", "tema": "Atención"},
        {"texto": "cuenta ahorros abrir requisitos saldo mínimo", "tema": "Cuentas"},
        {"texto": "CDT inversión tasa interés plazo rendimiento", "tema": "Inversión"},
        {"texto": "tarjeta crédito cuota manejo cupo disponible", "tema": "Tarjetas"},
        {"texto": "sucursales Cali horario atención dirección", "tema": "Sucursales"},
        {"texto": "crédito personal libre destino cuotas plazo", "tema": "Créditos"},
        {"texto": "bloquear tarjeta perdida robo emergencia", "tema": "Atención"},
        {"texto": "cuenta corriente empresas nómina transacciones", "tema": "Cuentas"},
        {"texto": "leasing financiero vehículo empresa activos", "tema": "Créditos"},
        {"texto": "fiducia inversión portafolio rendimientos patrimonio", "tema": "Inversión"},
        {"texto": "sucursales Bogotá Chapinero norte oficinas", "tema": "Sucursales"},
        {"texto": "tarjeta débito retiro cajero automático límite", "tema": "Tarjetas"},
        {"texto": "App móvil banca digital descarga problema error", "tema": "Digital"},
    ]

    result = []
    for i, s in enumerate(samples * 3):  # Triplicar para tener más datos
        result.append({
            "session_id": f"demo_{i}@example.com",
            "texto":      s["texto"],
            "n_turnos":   np.random.randint(1, 8),
            "mensajes":   [],
        })
    return result


# ══════════════════════════════════════════════════════════
# CLASIFICACIÓN DE TEMAS
# ══════════════════════════════════════════════════════════

def _classify_topic(texto: str) -> str:
    """Clasifica el tema de la conversación por palabras clave."""
    texto_lower = texto.lower()

    topics = {
        "💳 Tarjetas":     ["tarjeta", "occiflex", "cupo", "cuota manejo"],
        "🏠 Créditos":     ["crédito", "hipotecario", "préstamo", "cuota", "leasing"],
        "💰 Inversión":    ["cdt", "inversión", "rendimiento", "fiducia", "portafolio"],
        "🏦 Cuentas":      ["cuenta", "ahorros", "corriente", "saldo", "nómina"],
        "📞 Atención":     ["teléfono", "llamar", "asesor", "bloquear", "fraude", "emergencia"],
        "📍 Sucursales":   ["sucursal", "oficina", "horario", "cali", "bogotá", "dirección"],
        "📱 Digital":      ["app", "móvil", "digital", "banca web", "contraseña"],
    }

    for topic, keywords in topics.items():
        if any(kw in texto_lower for kw in keywords):
            return topic

    return "❓ Otros"


# ══════════════════════════════════════════════════════════
# GENERACIÓN DE EMBEDDINGS
# ══════════════════════════════════════════════════════════

def embed_conversations(conversations: list[dict]) -> np.ndarray:
    """
    Convierte cada conversación en un vector de 768 dimensiones
    usando Google text-embedding-004.
    """
    print(f"[tsne] Generando embeddings para {len(conversations)} conversaciones...")

    embedding_fn = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    model_kwargs={"device": "cpu"}
)

    textos = [c["texto"] for c in conversations]
    embeddings = []

    # Procesar en batches de 5 (límite conservador para la API)
    batch_size = 5
    for i in range(0, len(textos), batch_size):
        batch = textos[i:i + batch_size]
        try:
            batch_embs = embedding_fn.embed_documents(batch)
            embeddings.extend(batch_embs)
            print(f"  [{i + len(batch)}/{len(textos)}] embeddings generados")
        except Exception as e:
            print(f"  [!] Error en batch {i//batch_size + 1}: {e}")
            # Fallback: vector de ceros para este batch
            embeddings.extend([[0.0] * 768] * len(batch))

    return np.array(embeddings)


# ══════════════════════════════════════════════════════════
# t-SNE Y VISUALIZACIÓN
# ══════════════════════════════════════════════════════════

def run_tsne(embeddings: np.ndarray, n_components: int = 2) -> np.ndarray:
    """Aplica t-SNE para reducir dimensiones a 2D."""
    print(f"[tsne] Aplicando t-SNE ({embeddings.shape[0]} muestras, {embeddings.shape[1]} dims → 2D)...")

    # Normalizar antes de t-SNE
    scaler  = StandardScaler()
    emb_norm = scaler.fit_transform(embeddings)

    # Parámetros t-SNE para conversaciones
    perplexity = min(30, max(5, len(embeddings) // 3))

    tsne = TSNE(
        n_components=n_components,
        perplexity=perplexity,
        max_iter=1000,
        random_state=42,
        learning_rate="auto",
        init="pca",
    )
    reduced = tsne.fit_transform(emb_norm)
    print(f"[tsne] Reducción completada: {reduced.shape}")
    return reduced


def cluster_conversations(embeddings: np.ndarray, n_clusters: int = 6) -> np.ndarray:
    """Agrupa conversaciones con K-Means para identificar patrones."""
    n_clusters = min(n_clusters, len(embeddings))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return kmeans.fit_predict(embeddings)


def visualize(
    reduced: np.ndarray,
    conversations: list[dict],
    clusters: np.ndarray,
    output_path: str = "tsne_conversaciones.html",
):
    """Genera visualización interactiva con Plotly."""
    print("[tsne] Generando visualización interactiva...")

    # Clasificar temas por palabras clave
    topics = [_classify_topic(c["texto"]) for c in conversations]

    # Colores por cluster
    cluster_labels = [f"Cluster {c + 1}" for c in clusters]

    fig = go.Figure()

    # Un scatter por cada tema para la leyenda
    unique_topics = list(set(topics))
    colors = px.colors.qualitative.Bold

    for i, topic in enumerate(unique_topics):
        mask = [j for j, t in enumerate(topics) if t == topic]
        if not mask:
            continue

        fig.add_trace(go.Scatter(
            x=[reduced[j, 0] for j in mask],
            y=[reduced[j, 1] for j in mask],
            mode="markers",
            name=topic,
            marker=dict(
                size=[8 + min(c["n_turnos"], 10) for c in [conversations[j] for j in mask]],
                color=colors[i % len(colors)],
                opacity=0.8,
                line=dict(width=1, color="white"),
            ),
            text=[
                f"<b>{topic}</b><br>"
                f"Sesión: {conversations[j]['session_id'][:30]}<br>"
                f"Turnos: {conversations[j]['n_turnos']}<br>"
                f"Cluster: {cluster_labels[j]}<br>"
                f"Texto: {conversations[j]['texto'][:100]}..."
                for j in mask
            ],
            hoverinfo="text",
        ))

    fig.update_layout(
        title=dict(
            text="Análisis de Conversaciones — Asistente Virtual Banco de Occidente<br>"
                 "<sub>Cada punto es una conversación. Clusters revelan patrones de consulta.</sub>",
            font=dict(size=18, color="#001E55"),
            x=0.5,
        ),
        plot_bgcolor="#F4F7FB",
        paper_bgcolor="white",
        legend=dict(
            title="Temas detectados",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#E0EEF8",
            borderwidth=1,
        ),
        xaxis=dict(title="Dimensión t-SNE 1", showgrid=True, gridcolor="#E0EEF8"),
        yaxis=dict(title="Dimensión t-SNE 2", showgrid=True, gridcolor="#E0EEF8"),
        width=1100, height=700,
        font=dict(family="Inter, Arial", color="#1A2332"),
    )

    # Añadir anotaciones de clusters
    for cluster_id in range(max(clusters) + 1):
        mask_c = np.where(clusters == cluster_id)[0]
        if len(mask_c) == 0:
            continue
        cx = reduced[mask_c, 0].mean()
        cy = reduced[mask_c, 1].mean()
        fig.add_annotation(
            x=cx, y=cy,
            text=f"C{cluster_id + 1}",
            font=dict(size=11, color="#003DA5", family="Inter"),
            showarrow=False,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="#003DA5",
            borderwidth=1,
            borderpad=3,
        )

    plot(fig, filename=output_path, auto_open=True)
    print(f"[tsne] Visualización guardada: {output_path}")
    return output_path


# ══════════════════════════════════════════════════════════
# PIPELINE COMPLETO
# ══════════════════════════════════════════════════════════

def run_analysis(output_path: str = "tsne_conversaciones.html") -> str:
    """Ejecuta el pipeline completo de análisis t-SNE."""

    print("""
╔══════════════════════════════════════════════════════╗
║  ANÁLISIS t-SNE — Conversaciones BdO                ║
╚══════════════════════════════════════════════════════╝
""")

    # 1. Cargar conversaciones
    conversations = load_all_conversations()

    if len(conversations) < 5:
        print(f"[tsne] Solo {len(conversations)} conversaciones reales.")
        print("[tsne] Usando datos de demostración para visualización...")
        conversations = _generate_sample_data()
    else:
        print("[tsne] Usando datos reales para visualización...")

    # 2. Generar embeddings
    embeddings = embed_conversations(conversations)

    if embeddings.shape[0] == 0:
        print("[tsne] No se pudieron generar embeddings.")
        return ""

    # 3. t-SNE
    reduced = run_tsne(embeddings)

    # 4. Clustering
    n_clusters = min(6, len(conversations) // 3 + 1)
    clusters   = cluster_conversations(embeddings, n_clusters=n_clusters)

    # 5. Visualizar
    path = visualize(reduced, conversations, clusters, output_path)

    # 6. Reporte de clusters
    print("\n📊 RESUMEN DE CLUSTERS:")
    for c_id in range(max(clusters) + 1):
        mask    = [i for i, c in enumerate(clusters) if c == c_id]
        topics  = [_classify_topic(conversations[i]["texto"]) for i in mask]
        top_topic = max(set(topics), key=topics.count)
        print(f"  Cluster {c_id + 1}: {len(mask)} conversaciones | Tema dominante: {top_topic}")

    return path


if __name__ == "__main__":
    run_analysis()
