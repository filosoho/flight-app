import atexit
import os

from dotenv import load_dotenv
from psycopg2.pool import SimpleConnectionPool

load_dotenv()

connection_pool: SimpleConnectionPool | None = None


def init_pool() -> SimpleConnectionPool:
    global connection_pool

    if connection_pool is None:
        connection_pool = SimpleConnectionPool(
            1,
            10,
            host=os.environ["DB_HOST"],
            port=os.environ.get("DB_PORT", "5432"),
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )

    return connection_pool


def get_connection():
    pool = init_pool()
    return pool.getconn()


def release_connection(connection):
    connection_pool.putconn(connection)


def execute_query(
    query,
    params=None,
    fetch_one=False,
    fetch_all=False,
    returning=False,
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(query, params)

        if fetch_one:
            result = cursor.fetchone()
            return result

        if fetch_all:
            result = cursor.fetchall()
            return result

        if returning:
            result = cursor.fetchone()
            conn.commit()
            return result

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        release_connection(conn)


def close_pool():
    if connection_pool:
        connection_pool.closeall()


atexit.register(close_pool)
