from contextlib import contextmanager
from queue import Queue, Empty
import pyodbc
from app.core.config import settings


client_pool = Queue(maxsize=settings.POOL_SIZE)


def _build_conn_str() -> str:
    return (
        f"DRIVER={{{settings.DB_DRIVER}}};"
        f"SERVER={settings.DB_HOST};"
        f"DATABASE={settings.DB_NAME};"
        f"UID={settings.DB_USER};"
        f"PWD={settings.DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )


def _new_connection() -> pyodbc.Connection:
    return pyodbc.connect(_build_conn_str())


def init_pool():
    for _ in range(settings.POOL_SIZE):
        try:
            client_pool.put(_new_connection())
        except pyodbc.Error as e:
            print(f"Database connection error: {e}")
            raise


def close_pool():
    while not client_pool.empty():
        conn = client_pool.get()
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def db_client():
    try:
        conn = client_pool.get(timeout=settings.DB_POOL_TIMEOUT)
    except Empty:
        raise RuntimeError("No database connections available — pool exhausted")

    broken = False
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            broken = True
        raise
    finally:
        if broken:
            try:
                conn.close()
            except Exception:
                pass
            try:
                client_pool.put(_new_connection())
            except pyodbc.Error as e:
                print(f"Failed to replace broken pool connection: {e}")
                # don't re-raise here — swallowing would silently shrink the pool;
                # decide deliberately whether that's acceptable for your ops setup
        else:
            client_pool.put(conn)