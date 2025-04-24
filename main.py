from fastapi import FastAPI
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow React app to connect
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

def get_connection():
    return psycopg2.connect(
        database="book_notes",  # Hardcoded database name
        user="postgres",        # Hardcoded database user
        password="lolypop0",    # Hardcoded database password
        host="localhost",       # Hardcoded database host
        port="5432"             # Hardcoded database port
    )

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

# To run the app: uvicorn main:app --reload --port 8080
