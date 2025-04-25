from fastapi import FastAPI
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or whatever domain you’ll be using
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to Render PostgreSQL
def get_connection():
    return psycopg2.connect(
        dbname="pgadmin_mrsk",
        user="pgadmin_mrsk_user",
        password="MgrSF6CM1ybExuQWhBMHVCFLQH5CXmv5",
        host="dpg-d05caa24d50c73etcaj0-a.oregon-postgres.render.com",
        port="5432",
        sslmode="require"
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
    print(f"Search query received: {q}")  # helpful logging
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = "SELECT note_id, title FROM notes WHERE title ILIKE %s OR content ILIKE %s ORDER BY note_id ASC;"
    cur.execute(query, (f"%{q}%", f"%{q}%"))
    results = cur.fetchall()
    print(f"Search results: {results}")
    cur.close()
    conn.close()
    return {"results": results}
