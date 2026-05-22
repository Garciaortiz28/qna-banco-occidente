import os
import sys
import re
import time
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SCRAPING_DIR, ensure_dirs

ensure_dirs()

from dotenv import load_dotenv
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

CHANNEL_ID     = "UC7YOu9z6AfN8Hs9wEqKf5AQ"
CHANNEL_HANDLE = "@BancodeOccidenteCol"
CHANNEL_URL    = f"https://www.youtube.com/{CHANNEL_HANDLE}"

# Número máximo de videos a procesar (None = todos)
MAX_VIDEOS = None

# Preferencia de idioma para los subtítulos
LANG_PRIORITY = ["es", "es-419", "es-CO", "a.es", "a.es-419"]

OUTPUT_DIR     = os.path.join(SCRAPING_DIR, "youtube")
CATALOG_FILE   = os.path.join(OUTPUT_DIR, "_catalogo_videos.json")
REPORT_FILE    = os.path.join(OUTPUT_DIR, "_reporte.md")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def build_youtube_client():
    if not YOUTUBE_API_KEY:
        raise ValueError(
            "YOUTUBE_API_KEY no encontrada en .env\n"
            "Obtén una en: https://console.cloud.google.com/apis/library/youtube.googleapis.com"
        )
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def get_uploads_playlist(client) -> str:
    resp = client.channels().list(
        part="contentDetails,snippet",
        id=CHANNEL_ID
    ).execute()

    if not resp.get("items"):
        raise RuntimeError(f"Canal {CHANNEL_ID} no encontrado o sin acceso.")

    info = resp["items"][0]
    playlist_id = info["contentDetails"]["relatedPlaylists"]["uploads"]
    subs        = info["statistics"].get("subscriberCount", "N/A") if "statistics" in info else "N/A"
    total       = info["statistics"].get("videoCount", "N/A") if "statistics" in info else "N/A"

    print(f"  Canal:       {info['snippet']['title']}")
    print(f"  Suscriptores: {subs}")
    print(f"  Total videos: {total}")
    print(f"  Playlist:    {playlist_id}\n")
    return playlist_id


def list_all_videos(client, playlist_id: str) -> list:
    videos  = []
    token   = None

    while True:
        params = dict(part="snippet,contentDetails", playlistId=playlist_id, maxResults=50)
        if token:
            params["pageToken"] = token

        resp  = client.playlistItems().list(**params).execute()
        items = resp.get("items", [])

        for item in items:
            snip = item["snippet"]
            vid  = {
                "video_id":    snip["resourceId"]["videoId"],
                "title":       snip["title"],
                "description": snip.get("description", ""),
                "published_at": snip.get("publishedAt", ""),
                "url":         f"https://www.youtube.com/watch?v={snip['resourceId']['videoId']}",
                "thumbnail":   snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            }
            videos.append(vid)

        token = resp.get("nextPageToken")
        if not token:
            break

        time.sleep(0.2)

    return videos


def enrich_video_stats(client, videos: list) -> list:
    enriched = []
    for i in range(0, len(videos), 50):
        batch   = videos[i:i + 50]
        ids_str = ",".join(v["video_id"] for v in batch)
        resp    = client.videos().list(
            part="statistics,contentDetails",
            id=ids_str
        ).execute()

        stats_map = {
            item["id"]: {
                "views":    item["statistics"].get("viewCount", "0"),
                "likes":    item["statistics"].get("likeCount", "0"),
                "comments": item["statistics"].get("commentCount", "0"),
                "duration": item["contentDetails"].get("duration", "PT0S"),
            }
            for item in resp.get("items", [])
        }

        for vid in batch:
            vid.update(stats_map.get(vid["video_id"], {}))
            enriched.append(vid)

        time.sleep(0.2)

    return enriched


def parse_iso_duration(duration: str) -> str:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return "0:00"
    h, m, s = (int(x or 0) for x in match.groups())
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def get_transcript(video_id: str) -> tuple[str, str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
    except ImportError:
        return "", "youtube-transcript-api no instalado"

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        transcript = None
        lang_used  = ""

        for lang in LANG_PRIORITY:
            try:
                transcript = transcript_list.find_transcript([lang])
                lang_used  = lang
                break
            except Exception:
                pass

        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(["es", "es-419"])
                lang_used  = "auto-es"
            except Exception:
                pass

        if transcript is None:
            try:
                t = transcript_list.find_generated_transcript(["en"])
                transcript = t.translate("es")
                lang_used  = "traducido-en"
            except Exception:
                pass

        if transcript is None:
            return "", "sin-subtitulos"

        entries = transcript.fetch()
        raw     = " ".join(e["text"] for e in entries)
        clean   = clean_transcript(raw)
        return clean, lang_used

    except NoTranscriptFound:
        return "", "sin-subtitulos"
    except Exception as e:
        return "", f"error: {str(e)[:60]}"


def clean_transcript(raw: str) -> str:
    text = re.sub(r'\[.*?\]', '', raw)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'♪[^♪]*♪', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(?<=[.!?])\s+', '\n\n', text)
    return text.strip()


def to_markdown(video: dict, transcript: str, lang: str) -> str:
    pub_date = ""
    if video.get("published_at"):
        try:
            dt       = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
            pub_date = dt.strftime("%d/%m/%Y")
        except Exception:
            pub_date = video["published_at"][:10]

    duration = parse_iso_duration(video.get("duration", "PT0S"))
    views    = int(video.get("views", 0))
    likes    = int(video.get("likes", 0))

    lines = [
        f"# {video['title']}",
        f"",
        f"**Fuente:** YouTube — Banco de Occidente  ",
        f"**URL:** {video['url']}  ",
        f"**Publicado:** {pub_date}  ",
        f"**Duración:** {duration}  ",
        f"**Vistas:** {views:,}  |  **Likes:** {likes:,}  ",
        f"**Subtítulos:** {lang}",
        f"",
    ]

    if video.get("description", "").strip():
        desc = video["description"][:800].strip()
        lines += [
            "## Descripción del video",
            "",
            desc,
            "",
        ]

    if transcript:
        lines += [
            "## Transcripción",
            "",
            transcript,
            "",
        ]
    else:
        lines += [
            "## Transcripción",
            "",
            "_Video sin subtítulos disponibles en español._",
            "",
        ]

    return "\n".join(lines)


def save_video(video: dict, transcript: str, lang: str):
    safe_title = re.sub(r'[^\w\s-]', '', video['title'])
    safe_title = re.sub(r'\s+', '_', safe_title.strip())[:80]
    filename   = f"yt_{video['video_id']}_{safe_title}.txt"
    filepath   = os.path.join(OUTPUT_DIR, filename)

    content = f"URL: {video['url']}\n\n" + to_markdown(video, transcript, lang)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def generate_report(videos: list, stats: dict):
    total      = stats["total"]
    with_trans = stats["with_transcript"]
    no_trans   = stats["no_transcript"]
    errors     = stats["errors"]
    total_min  = stats["total_minutes"]

    lines = [
        "# Reporte — Canal YouTube Banco de Occidente",
        f"",
        f"**Canal:** {CHANNEL_URL}  ",
        f"**Generado:** {datetime.now().strftime('%d/%m/%Y %H:%M')}  ",
        f"",
        "## Resumen",
        f"",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Videos procesados | {total} |",
        f"| Con transcripción | {with_trans} |",
        f"| Sin transcripción | {no_trans} |",
        f"| Errores | {errors} |",
        f"| Duración total estimada | {total_min:.0f} min |",
        f"",
        "## Catálogo de videos",
        f"",
    ]

    for vid in sorted(videos, key=lambda v: v.get("published_at", ""), reverse=True):
        pub = vid.get("published_at", "")[:10]
        views = int(vid.get("views", 0))
        marker = "✓" if vid.get("_has_transcript") else "✗"
        lines.append(f"- [{marker}] **{vid['title']}** ({pub}) — {views:,} vistas  ")
        lines.append(f"  {vid['url']}")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n  Reporte guardado: {REPORT_FILE}")


def run():
    print("\n=== YOUTUBE SCRAPER — Banco de Occidente ===")
    print(f"  Canal: {CHANNEL_URL}\n")

    client      = build_youtube_client()
    playlist_id = get_uploads_playlist(client)

    print("  Obteniendo lista de videos...")
    videos = list_all_videos(client, playlist_id)
    print(f"  {len(videos)} videos encontrados")

    print("  Enriqueciendo con estadísticas...")
    videos = enrich_video_stats(client, videos)

    if MAX_VIDEOS:
        videos = videos[:MAX_VIDEOS]
        print(f"  Limitado a {MAX_VIDEOS} videos (MAX_VIDEOS)")

    print(f"\n  Descargando transcripciones...\n")

    stats = {"total": 0, "with_transcript": 0, "no_transcript": 0,
             "errors": 0, "total_minutes": 0}
    catalog = []

    for i, video in enumerate(videos, 1):
        title = video["title"][:55]
        print(f"  [{i:>3}/{len(videos)}] {title:<55}", end=" ")

        transcript, lang = get_transcript(video["video_id"])

        duration_s = 0
        d = video.get("duration", "PT0S")
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
        if m:
            h, mn, s = (int(x or 0) for x in m.groups())
            duration_s = h * 3600 + mn * 60 + s
        stats["total_minutes"] += duration_s / 60

        if transcript:
            stats["with_transcript"] += 1
            video["_has_transcript"] = True
            print(f"✓ {lang}")
        elif "error" in lang:
            stats["errors"] += 1
            video["_has_transcript"] = False
            print(f"✗ {lang}")
        else:
            stats["no_transcript"] += 1
            video["_has_transcript"] = False
            print("✗ sin subtítulos")

        save_video(video, transcript, lang)
        catalog.append(video)
        stats["total"] += 1

        time.sleep(0.5)

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        safe_catalog = [{k: v for k, v in vid.items() if not k.startswith("_")}
                        for vid in catalog]
        json.dump(safe_catalog, f, ensure_ascii=False, indent=2)

    generate_report(catalog, stats)

    print(f"\n{'='*50}")
    print(f"  Videos procesados:    {stats['total']}")
    print(f"  Con transcripción:    {stats['with_transcript']}")
    print(f"  Sin transcripción:    {stats['no_transcript']}")
    print(f"  Duración total:       {stats['total_minutes']:.0f} min")
    print(f"  Archivos en:          {OUTPUT_DIR}")
    print(f"{'='*50}")
    print("\nSiguiente paso: python main.py --step clean\n")


if __name__ == "__main__":
    run()
