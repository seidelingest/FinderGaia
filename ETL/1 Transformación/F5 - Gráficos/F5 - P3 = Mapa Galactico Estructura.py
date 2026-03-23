# ==========================================================
# ETL F5:P3 -> MAPA GALÁCTICO (PROGRESO SIMPLE)
# ==========================================================

import time
import numpy as np
from pymongo import MongoClient, InsertOne

# ==========================================================
# CONFIG
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"

SOURCE_COLLECTION = "Gaia DR3"
TARGET_COLLECTION = "F5:P3 -> Mapa Galactico Estructura"

FIELD_RA = "ra"
FIELD_DEC = "dec"
FIELD_PARALLAX = "parallax"
FIELD_POE = "parallax_over_error"
FIELD_BP_RP = "bp_rp"

MAX_BP_RP = 0.8
MIN_POE = 3.0
MAX_DISTANCE_KPC = 8.0

READ_BLOCK = 300_000
WRITE_BATCH = 20_000
PRINT_STEP = 2_000_000

EQ_TO_GAL = np.array([
    [-0.0548755604, -0.8734370902, -0.4838350155],
    [ 0.4941094279, -0.4448296300,  0.7469822445],
    [-0.8676661490, -0.1980763734,  0.4559837762]
], dtype=np.float64)

SUN_DISTANCE_KPC = 8.2

# ==========================================================
# INICIO
# ==========================================================

print("========================================================")
print(" ETL MAPA GALÁCTICO (PROGRESO SIMPLE)")
print("========================================================")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

source = db[SOURCE_COLLECTION]
target = db[TARGET_COLLECTION]

print("Recreando colección destino...")
target.drop()

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

cursor = source.find(query, projection, batch_size=300_000)

read_block = []
write_ops = []

total = 0
inserted = 0

t_start = time.time()

# ==========================================================
# LOOP
# ==========================================================

for doc in cursor:

    read_block.append(doc)
    total += 1

    if len(read_block) >= READ_BLOCK:

        ra = np.array([d["ra"] for d in read_block])
        dec = np.array([d["dec"] for d in read_block])
        parallax = np.array([d["parallax"] for d in read_block])

        distance_kpc = (1000.0 / parallax) / 1000.0

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

            write_ops.extend(
                InsertOne({"X": float(X[i]), "Y": float(Y[i])})
                for i in range(len(X))
            )

        read_block.clear()

        if len(write_ops) >= WRITE_BATCH:
            result = target.bulk_write(write_ops, ordered=False)
            inserted += result.inserted_count
            write_ops.clear()

    # ------------------------------------------------------
    # LOG SIMPLE
    # ------------------------------------------------------

    if total % PRINT_STEP == 0:
        dt = time.time() - t_start
        speed = total / dt if dt > 0 else 0

        print(
            f"{total:,} leídos | "
            f"{inserted:,} insertados | "
            f"{speed:,.0f} docs/s"
        )

# ==========================================================
# FINAL
# ==========================================================

if write_ops:
    result = target.bulk_write(write_ops, ordered=False)
    inserted += result.inserted_count

cursor.close()

target.create_index([("X", 1), ("Y", 1)])

t_total = (time.time() - t_start) / 60

print("\n========================================================")
print(" ETL FINALIZADA")
print("========================================================")
print(f"Leídos: {total:,}")
print(f"Insertados: {inserted:,}")
print(f"Tiempo: {t_total:.2f} min")
print("========================================================")