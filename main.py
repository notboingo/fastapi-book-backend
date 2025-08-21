# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import time

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======= your current credentials (as you requested) =======
DB_NAME = "pgadmin_mrsk"
DB_USER = "pgadmin_mrsk_user"
DB_PASSWORD = "MgrSF6CM1ybExuQWhBMHVCFLQH5CXmv5"
DB_HOST_EXTERNAL = "dpg-d05caa24d50c73etcaj0-a.oregon-postgres.render.com"  # external hostname
DB_HOST_INTERNAL = "dpg-d05caa24d50c73etcaj0-a"  # internal host (same prefix, no domain)
DB_PORT = "5432"
# ===========================================================

def dsn_internal():
    # Internal URL is reachable only from Render services in the same region.
    # It typically does NOT use SSL.
    return (
        f"host={DB_HOST_INTERNAL} port={DB_PORT} "
        f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} "
        f"sslmode=disable"
    )

def dsn_external():
    # External URL requires SSL
    return (
        f"host={DB_HOST_EXTERNAL} port={DB_PORT} "
        f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} "
        f"sslmode=require"
    )

POOL: SimpleConnectionPool | None = None

def try_make_pool(dsn: str) -> SimpleConnectionPool:
    pool = SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=dsn,
        connect_timeout=5,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    # pre-warm
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
    finally:
        pool.putconn(conn)
    return pool

def init_pool_with_fallback():
    # 1) Try internal (no SSL) for in-Render connectivity
    # 2) Fallback to external (SSL) if internal is not reachable
    last_err = None
    for dsn in (dsn_internal(), dsn_external()):
        try:
            return try_make_pool(dsn)
        except Exception as e:
            last_err = e
            time.sleep(0.6)
    raise last_err

def get_conn():
    assert POOL is not None, "DB pool not initialized"
    conn = POOL.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")  # pre-ping
        return conn
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
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
    global POOL
    POOL = init_pool_with_fallback()

@app.on_event("shutdown")
def on_shutdown():
    global POOL
    if POOL:
        POOL.closeall()
        POOL = None

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/dbhealth")
def dbhealth():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("select inet_server_addr(), version();")
            host_ip, ver = cur.fetchone()
        put_conn(conn)
        return {"db_ok": True, "server_ip": str(host_ip), "version": ver}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB not reachable: {e}")

@app.get("/notes")
def list_notes():
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT note_id, title FROM notes ORDER BY note_id ASC;")
            rows = cur.fetchall()
        put_conn(conn)
        return {"notes": rows}
    except psycopg2.OperationalError:
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