#!/usr/bin/env python3
"""
Change Data Collector: Oracle → Redis.
Sincroniza cada 30 segundos solo los registros modificados desde Oracle a Redis.
Requiere que la tabla Oracle tenga una columna de auditoría (ej. UPDATED_AT).
Uso: pip install oracledb redis && python oracle_redis_cdc.py
"""

import json
import os
import time
from datetime import datetime

import oracledb
import redis

# --- Configuración (ajustar o usar variables de entorno) ---
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/ORCLPDB1")
ORACLE_USER = os.getenv("ORACLE_USER", "mi_usuario")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "mi_password")
ORACLE_TABLE = os.getenv("ORACLE_TABLE", "MI_CATALOGO")
ORACLE_KEY_COLUMN = os.getenv("ORACLE_KEY_COLUMN", "ID")
ORACLE_CHANGE_COLUMN = os.getenv("ORACLE_CHANGE_COLUMN", "UPDATED_AT")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "catalog")
INTERVAL_SECONDS = int(os.getenv("CDC_INTERVAL_SECONDS", "30"))

# Clave en Redis donde guardamos la última fecha de sincronización
LAST_SYNC_KEY = f"{REDIS_PREFIX}:{ORACLE_TABLE}:last_sync"


def get_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_last_sync(r: redis.Redis):
    val = r.get(LAST_SYNC_KEY)
    if val is None:
        return None
    return val


def set_last_sync(r: redis.Redis, ts: str):
    r.set(LAST_SYNC_KEY, ts)


def run_sync():
    r = get_redis()
    last_sync = get_last_sync(r)

    conn = oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
    cursor = conn.cursor()

    # Solo registros modificados después de last_sync
    if last_sync:
        sql = f"""
            SELECT * FROM {ORACLE_TABLE}
            WHERE {ORACLE_CHANGE_COLUMN} > TO_TIMESTAMP(:last_sync, 'YYYY-MM-DD HH24:MI:SS.FF')
            ORDER BY {ORACLE_CHANGE_COLUMN}
        """
        cursor.execute(sql, last_sync=last_sync)
    else:
        # Primera ejecución: traer todo (o las últimas 24h según prefieras)
        sql = f"SELECT * FROM {ORACLE_TABLE} ORDER BY {ORACLE_CHANGE_COLUMN}"
        cursor.execute(sql)

    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    now_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:23]
    key_col_idx = columns.index(ORACLE_KEY_COLUMN.upper())

    pipe = r.pipeline()
    for row in rows:
        record = dict(zip(columns, (str(v) if v is not None else "" for v in row)))
        key_id = record[ORACLE_KEY_COLUMN.upper()]
        redis_key = f"{REDIS_PREFIX}:{ORACLE_TABLE}:{key_id}"
        pipe.set(redis_key, json.dumps(record, default=str))
    pipe.set(LAST_SYNC_KEY, now_ts)
    pipe.execute()

    return len(rows), now_ts


def main():
    print(f"CDC Oracle → Redis. Tabla={ORACLE_TABLE}, intervalo={INTERVAL_SECONDS}s")
    while True:
        try:
            updated, ts = run_sync()
            if updated > 0:
                print(f"{datetime.now().isoformat()} — Actualizados {updated} registros en Redis (last_sync={ts})")
        except Exception as e:
            print(f"{datetime.now().isoformat()} — Error: {e}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
