import psycopg, os
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv('SUPABASE_DB_URI')
conn = psycopg.connect(uri, autocommit=True)
cur = conn.cursor()

# Limpiar TODAS las tablas de LangGraph
cur.execute("DELETE FROM checkpoint_writes;")
print("checkpoint_writes:", cur.statusmessage)
cur.execute("DELETE FROM checkpoint_blobs;")
print("checkpoint_blobs:", cur.statusmessage)
cur.execute("DELETE FROM checkpoints;")
print("checkpoints:", cur.statusmessage)

conn.close()
print("Listo — historial completamente limpio")