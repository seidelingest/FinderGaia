# ==========================================================
# ETL F4:P3 -> 5D ESPACIO FÍSICO COMPLETO (OPTIMIZADO PRO)
# ==========================================================

import time
import numpy as np
from pymongo import MongoClient, InsertOne

# ==========================================================
# CONFIG
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/?compressors=zstd"
DB_NAME = "TFM"

SOURCE_COLLECTION = "Gaia DR3"
TARGET_COLLECTION = "F4:P3 -> 5D Espacio Físico Completo"

READ_BATCH = 50_000       # ↓ reduce latencia inicial
WRITE_BATCH = 20_000      # ↓ evita bloqueos largos
PRINT_STEP = 1_000_000

K = 4.74047

# ==========================================================
# CONEXIÓN (WRITE OPTIMIZADO)
# ==========================================================

client = MongoClient(MONGO_URI, w=0)
db = client[DB_NAME]

source = db[SOURCE_COLLECTION]
target = db[TARGET_COLLECTION]

print("Limpiando colección destino...")
target.drop()

# ==========================================================
# QUERY
# ==========================================================

query = {
    "parallax": {"$gt": 0},
    "parallax_over_error": {"$gt": 2},
    "pmra": {"$ne": None},
    "pmdec": {"$ne": None},
    "ra": {"$ne": None},
    "dec": {"$ne": None}
}

projection = {
    "_id": 0,
    "source_id": 1,
    "ra": 1,
    "dec": 1,
    "parallax": 1,
    "pmra": 1,
    "pmdec": 1,
    "phot_bp_mean_mag": 1,
    "phot_rp_mean_mag": 1,
    "bp_rp": 1,
    "parallax_over_error": 1
}

# ==========================================================
# MATRIZ ROTACIÓN
# ==========================================================

EQ_TO_GAL = np.array([
    [-0.05487556, -0.87343709, -0.48383502],
    [ 0.49410943, -0.44482963,  0.74698225],
    [-0.86766615, -0.19807637,  0.45598378]
], dtype=np.float64)

# ==========================================================
# PROCESAMIENTO VECTORIAL (OPTIMIZADO)
# ==========================================================

def process_batch(batch):
    if not batch:
        return []

    ra = np.radians(np.fromiter((d["ra"] for d in batch), dtype=np.float64))
    dec = np.radians(np.fromiter((d["dec"] for d in batch), dtype=np.float64))
    parallax = np.fromiter((d["parallax"] for d in batch), dtype=np.float64)
    pmra = np.fromiter((d["pmra"] for d in batch), dtype=np.float64)
    pmdec = np.fromiter((d["pmdec"] for d in batch), dtype=np.float64)

    # Distancia
    dist = 1000.0 / parallax

    # Coordenadas ecuatoriales
    cos_dec = np.cos(dec)
    x_eq = dist * cos_dec * np.cos(ra)
    y_eq = dist * cos_dec * np.sin(ra)
    z_eq = dist * np.sin(dec)

    coords_eq = np.vstack((x_eq, y_eq, z_eq))
    coords_gal = EQ_TO_GAL @ coords_eq

    x, y, z = coords_gal

    # Velocidades
    v_ra = K * pmra / parallax
    v_dec = K * pmdec / parallax

    vx = v_ra * np.cos(ra)
    vy = v_ra * np.sin(ra)
    vz = v_dec

    docs = []

    for i, d in enumerate(batch):
        docs.append({
            "source_id": d["source_id"],

            # Posición
            "x": float(x[i]),
            "y": float(y[i]),
            "z": float(z[i]),

            # Velocidad
            "vx": float(vx[i]),
            "vy": float(vy[i]),
            "vz": float(vz[i]),

            # Fotometría
            "bp_rp": d.get("bp_rp"),
            "phot_bp_mean_mag": d.get("phot_bp_mean_mag"),
            "phot_rp_mean_mag": d.get("phot_rp_mean_mag"),

            # Calidad
            "parallax": d["parallax"],
            "parallax_over_error": d.get("parallax_over_error"),

            "quality": "balanced"
        })

    return docs

# ==========================================================
# LOOP PRINCIPAL (CON SESSION)
# ==========================================================

count_read = 0
count_inserted = 0

batch = []
ops = []

start = time.time()
last_print = 0

print("Iniciando cursor...")

with client.start_session() as session:

    cursor = source.find(
        query,
        projection,
        no_cursor_timeout=True,
        session=session
    ).batch_size(READ_BATCH)

    print("Procesando...")

    for doc in cursor:
        batch.append(doc)

        if len(batch) >= READ_BATCH:

            docs = process_batch(batch)

            for d in docs:
                ops.append(InsertOne(d))

                if len(ops) >= WRITE_BATCH:
                    target.bulk_write(ops, ordered=False)
                    count_inserted += len(ops)
                    ops = []

            count_read += len(batch)
            batch = []

            if count_read - last_print >= PRINT_STEP:
                elapsed = time.time() - start
                print(
                    f"Leídos: {count_read:,} | Insertados: {count_inserted:,} | "
                    f"Proc/s: {count_read/elapsed:,.0f} | Ins/s: {count_inserted/elapsed:,.0f}"
                )
                last_print = count_read

    # Últimos registros
    if batch:
        docs = process_batch(batch)
        ops.extend([InsertOne(d) for d in docs])
        count_read += len(batch)

    if ops:
        target.bulk_write(ops, ordered=False)
        count_inserted += len(ops)

    cursor.close()

# ==========================================================
# FINAL
# ==========================================================

elapsed = time.time() - start

print("\n================ FINAL ================")
print(f"Leídos totales: {count_read:,}")
print(f"Insertados totales: {count_inserted:,}")
print(f"Tiempo total: {elapsed:.2f} s")
print(f"Velocidad media proc: {count_read/elapsed:,.0f} reg/s")
print(f"Velocidad media ins: {count_inserted/elapsed:,.0f} reg/s")
print("======================================")
print("ETL COMPLETADO")