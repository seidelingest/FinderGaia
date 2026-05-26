# ==========================================================
# ETL F5:P4 -> MAPA GALÁCTICO (OPTIMIZADO + METRICS)
# ==========================================================

import time
import numpy as np
from pymongo import MongoClient

# ==========================================================
# CONFIG
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"

SOURCE_COLLECTION = "Gaia DR3"
TARGET_COLLECTION = "F5:P4 -> Mapa Galactico Estructura"

FIELD_RA = "ra"
FIELD_DEC = "dec"
FIELD_PARALLAX = "parallax"
FIELD_POE = "parallax_over_error"
FIELD_BP_RP = "bp_rp"

MAX_BP_RP = 0.8
MIN_POE = 3.0
MAX_DISTANCE_KPC = 8.0

READ_BLOCK = 1_000_000
WRITE_BATCH = 100_000
PRINT_STEP = 1_000_000

SUN_DISTANCE_KPC = 8.2

# ==========================================================
# MATRIZ ROTACIÓN
# ==========================================================

EQ_TO_GAL = np.array([
    [-0.0548755604, -0.8734370902, -0.4838350155],
    [ 0.4941094279, -0.4448296300,  0.7469822445],
    [-0.8676661490, -0.1980763734,  0.4559837762]
], dtype=np.float64)

# ==========================================================
# INICIO
# ==========================================================

print("========================================================")
print(" ETL MAPA GALÁCTICO (OPTIMIZADO)")
print("========================================================")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

source = db[SOURCE_COLLECTION]
target = db[TARGET_COLLECTION]

print("Recreando colección destino...")
target.drop()

# ==========================================================
# QUERY
# ==========================================================

query = {
    FIELD_BP_RP: {"$lt": MAX_BP_RP},
    FIELD_PARALLAX: {"$gt": 0},
    FIELD_POE: {"$gte": MIN_POE}
}

projection = {
    "_id": 0,
    FIELD_RA: 1,
    FIELD_DEC: 1,
    FIELD_PARALLAX: 1
}

print("Iniciando cursor...")
cursor = source.find(query, projection, no_cursor_timeout=True)\
               .batch_size(READ_BLOCK)

# ==========================================================
# VARIABLES
# ==========================================================

read_block = []
write_buffer = []

total_read = 0
total_inserted = 0

start_time = time.time()
last_print = 0

print("Procesando...")

# ==========================================================
# LOOP PRINCIPAL
# ==========================================================

for doc in cursor:

    read_block.append(doc)
    total_read += 1

    # ------------------------------------------------------
    # PROCESAMIENTO BLOQUE
    # ------------------------------------------------------
    if len(read_block) >= READ_BLOCK:

        ra = np.array([d["ra"] for d in read_block], dtype=np.float64)
        dec = np.array([d["dec"] for d in read_block], dtype=np.float64)
        parallax = np.array([d["parallax"] for d in read_block], dtype=np.float64)

        # Distancia simplificada (kpc)
        distance_kpc = 1.0 / parallax

        # Filtro distancia
        mask = distance_kpc < MAX_DISTANCE_KPC

        if np.any(mask):

            ra = ra[mask]
            dec = dec[mask]
            distance_kpc = distance_kpc[mask]

            ra_rad = np.deg2rad(ra)
            dec_rad = np.deg2rad(dec)

            cos_dec = np.cos(dec_rad)

            x = cos_dec * np.cos(ra_rad)
            y = cos_dec * np.sin(ra_rad)
            z = np.sin(dec_rad)

            vec = np.column_stack((x, y, z))
            gal = vec @ EQ_TO_GAL.T

            xh = distance_kpc * gal[:, 0]
            yh = distance_kpc * gal[:, 1]

            X = SUN_DISTANCE_KPC - xh
            Y = yh

            # Crear docs eficientes
            docs = [{"X": float(x), "Y": float(y)} for x, y in zip(X, Y)]
            write_buffer.extend(docs)

        read_block.clear()

    # ------------------------------------------------------
    # ESCRITURA
    # ------------------------------------------------------
    if len(write_buffer) >= WRITE_BATCH:
        result = target.insert_many(write_buffer, ordered=False)
        total_inserted += len(result.inserted_ids)
        write_buffer.clear()

    # ------------------------------------------------------
    # LOG EFICIENTE
    # ------------------------------------------------------
    if total_read - last_print >= PRINT_STEP:
        elapsed = time.time() - start_time

        proc_speed = total_read / elapsed if elapsed > 0 else 0
        ins_speed = total_inserted / elapsed if elapsed > 0 else 0

        print(
            f"Leídos: {total_read:,} | "
            f"Insertados: {total_inserted:,} | "
            f"Proc/s: {proc_speed:,.0f} | "
            f"Ins/s: {ins_speed:,.0f}"
        )

        last_print = total_read

# ==========================================================
# FINAL
# ==========================================================

# Último bloque
if read_block:

    ra = np.array([d["ra"] for d in read_block], dtype=np.float64)
    dec = np.array([d["dec"] for d in read_block], dtype=np.float64)
    parallax = np.array([d["parallax"] for d in read_block], dtype=np.float64)

    distance_kpc = 1.0 / parallax
    mask = distance_kpc < MAX_DISTANCE_KPC

    if np.any(mask):
        ra = ra[mask]
        dec = dec[mask]
        distance_kpc = distance_kpc[mask]

        ra_rad = np.deg2rad(ra)
        dec_rad = np.deg2rad(dec)

        cos_dec = np.cos(dec_rad)

        x = cos_dec * np.cos(ra_rad)
        y = cos_dec * np.sin(ra_rad)
        z = np.sin(dec_rad)

        vec = np.column_stack((x, y, z))
        gal = vec @ EQ_TO_GAL.T

        xh = distance_kpc * gal[:, 0]
        yh = distance_kpc * gal[:, 1]

        X = SUN_DISTANCE_KPC - xh
        Y = yh

        docs = [{"X": float(x), "Y": float(y)} for x, y in zip(X, Y)]
        write_buffer.extend(docs)

# Última escritura
if write_buffer:
    result = target.insert_many(write_buffer, ordered=False)
    total_inserted += len(result.inserted_ids)

cursor.close()

# Índice final
print("Creando índice...")
target.create_index([("X", 1), ("Y", 1)])

# ==========================================================
# RESUMEN FINAL
# ==========================================================

elapsed = time.time() - start_time

print("\n========================================================")
print(" ETL FINALIZADA")
print("========================================================")
print(f"Leídos: {total_read:,}")
print(f"Insertados: {total_inserted:,}")
print(f"Tiempo: {elapsed/60:.2f} min")
print(f"Velocidad proc: {total_read/elapsed:,.0f} reg/s")
print(f"Velocidad ins: {total_inserted/elapsed:,.0f} reg/s")
print("========================================================")