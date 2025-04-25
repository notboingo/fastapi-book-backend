import os
from fastapi import FastAPI
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://frontend-book-notes.vercel.app"],  # Allow React app to connect
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

def get_connection():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

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
