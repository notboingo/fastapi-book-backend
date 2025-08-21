# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import time

app = FastAPI()

# ----- CORS (tighten allow_origins later) -----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== YOUR CURRENT CREDS (kept as requested) ========
DB_NAME = "pgadmin_mrsk"
DB_USER = "pgadmin_mrsk_user"
DB_PASSWORD = "MgrSF6CM1ybExuQWhBMHVCFLQH5CXmv5"
DB_HOST = "dpg-d05caa24d50c73etcaj0-a.oregon-postgres.render.com"
DB_PORT = "5432"
# ========================================================

# Build a DSN with SSL required
DSN = (
    f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} "
    f"host={DB_HOST} port={DB_PORT} sslmode=require"
)

# Global pool
POOL: SimpleConnectionPool | None = None


def init_pool_with_retry(tries: int = 3, delay_sec: float = 0.8):
    """
    Initialize a small connection pool.
    Retries help ride out brief DB restarts / cold starts.
    """
    global POOL
    last_err = None
    for _ in range(tries):
        try:
            POOL = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DSN,
                connect_timeout=5,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            # Pre-warm one connection so we fail fast if DB is unreachable
            conn = POOL.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                return  # success
            finally:
                POOL.putconn(conn)
        except Exception as e:
            last_err = e
            time.sleep(delay_sec)
    # If we reach here, pool init failed after retries
    raise last_err


def get_conn():
    """
    Get a pooled connection and 'pre-ping' it.
    If the pool hands us a dead connection (after provider drops idles),
    replace it with a fresh one.
    """
    assert POOL is not None, "DB pool not initialized"
    conn = POOL.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")  # pre-ping validates socket
        return conn
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        # Try once more: get a brand new connection from the pool
        conn2 = POOL.getconn()
        with conn2.cursor() as cur:
            cur.execute("SELECT 1;")
        return conn2


def put_conn(conn):
    try:
        assert POOL is not None
        POOL.putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


@app.on_event("startup")
def on_startup():
    init_pool_with_retry()


@app.on_event("shutdown")
def on_shutdown():
    global POOL
    if POOL is not None:
        POOL.closeall()
        POOL = None


# ---------- Health endpoints ----------
@app.get("/healthz")
def healthz():
    # Simple health: doesn't touch DB
    return {"ok": True}


@app.get("/dbhealth")
def dbhealth():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT now();")
            ts = cur.fetchone()[0]
        put_conn(conn)
        return {"db_ok": True, "time": str(ts)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB not reachable: {e}")


# ---------- App endpoints ----------
@app.get("/notes")
def list_notes():
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT note_id, title FROM notes ORDER BY note_id ASC;"
            )
            rows = cur.fetchall()
        put_conn(conn)
        return {"notes": rows}
    except psycopg2.OperationalError:
        # Typical when provider restarts / SSL session closed
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notes/{note_id}")
def get_note(note_id: int):
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT note_id, title, content FROM notes WHERE note_id = %s;",
                (note_id,),
            )
            row = cur.fetchone()
        put_conn(conn)
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        return row
    except psycopg2.OperationalError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
def search_notes(q: str):
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT note_id, title
                FROM notes
                WHERE title ILIKE %s OR content ILIKE %s
                ORDER BY note_id ASC;
                """,
                (f"%{q}%", f"%{q}%"),
            )
            rows = cur.fetchall()
        put_conn(conn)
        return {"results": rows}
    except psycopg2.OperationalError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))