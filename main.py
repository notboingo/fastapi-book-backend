from fastapi import FastAPI
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Update later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection():
    return psycopg2.connect(os.getenv("postgresql://pgadmin_mrsk_user:MgrSF6CM1ybExuQWhBMHVCFLQH5CXmv5@dpg-d05caa24d50c73etcaj0-a.oregon-postgres.render.com/pgadmin_mrsk"))

@app.get("/notes")
def list_notes():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT note_id, title FROM notes ORDER BY note_id ASC;")
    notes = cur.fetchall()
    cur.close()
    conn.close()
    return notes

@app.get("/notes/{note_id}")
def get_note(note_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT note_id, title, content FROM notes WHERE note_id = %s;", (note_id,))
    note = cur.fetchone()
    cur.close()
    conn.close()
    return note

@app.get("/search")
def search_notes(q: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT note_id, title FROM notes WHERE search_vector @@ plainto_tsquery(%s)", (q,))
    results = [{"id": row[0], "title": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return {"results": results}
