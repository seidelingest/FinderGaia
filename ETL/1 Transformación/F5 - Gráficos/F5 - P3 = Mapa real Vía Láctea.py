# ==========================================================
# ETL F5:P3 -> MAPA REAL VIA LACTEA (BASE, ESTABLE)
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
TARGET_COLLECTION = "F5:P3 -> Mapa Real Via Lactea"

FIELD_SOURCE_ID = "source_id"
FIELD_RA = "ra"
FIELD_DEC = "dec"
FIELD_PARALLAX = "parallax"
FIELD_PARALLAX_OVER_ERROR = "parallax_over_error"
FIELD_BP_RP = "bp_rp"
FIELD_GMAG = "phot_g_mean_mag"

SUN_DISTANCE_KPC = 8.2
SUN_HEIGHT_KPC = 0.02

MAX_BP_RP = 0.5
MIN_PARALLAX_OVER_ERROR = 5.0
MAX_ABS_MAG_G = 3.0

READ_BLOCK_SIZE = 200_000
WRITE_BATCH_SIZE = 20_000
PRINT_STEP = 2_000_000

# ==========================================================
# MATRIZ
# ==========================================================

EQ_TO_GAL = np.array([
    [-0.0548755604, -0.8734370902, -0.4838350155],
    [ 0.4941094279, -0.4448296300,  0.7469822445],
    [-0.8676661490, -0.1980763734,  0.4559837762]
], dtype=np.float64)

# ==========================================================
# TRANSFORMACIÓN
# ==========================================================

def process_block(block):

    if not block:
        return []

    source_ids = []
    ra_vals = []
    dec_vals = []
    parallax_vals = []
    poe_vals = []
    bp_rp_vals = []
    gmag_vals = []

    for doc in block:
        source_ids.append(doc.get(FIELD_SOURCE_ID))
        ra_vals.append(doc.get(FIELD_RA))
        dec_vals.append(doc.get(FIELD_DEC))
        parallax_vals.append(doc.get(FIELD_PARALLAX))
        poe_vals.append(doc.get(FIELD_PARALLAX_OVER_ERROR))
        bp_rp_vals.append(doc.get(FIELD_BP_RP))
        gmag_vals.append(doc.get(FIELD_GMAG))

    ra_vals = np.array(ra_vals, dtype=np.float64)
    dec_vals = np.array(dec_vals, dtype=np.float64)
    parallax_vals = np.array(parallax_vals, dtype=np.float64)
    poe_vals = np.array(poe_vals, dtype=np.float64)
    bp_rp_vals = np.array(bp_rp_vals, dtype=np.float64)
    gmag_vals = np.array(gmag_vals, dtype=np.float64)

    valid = (
        np.isfinite(ra_vals) &
        np.isfinite(dec_vals) &
        np.isfinite(parallax_vals) &
        np.isfinite(poe_vals) &
        np.isfinite(bp_rp_vals) &
        np.isfinite(gmag_vals) &
        (parallax_vals > 0) &
        (poe_vals >= MIN_PARALLAX_OVER_ERROR) &
        (bp_rp_vals < MAX_BP_RP)
    )

    if not np.any(valid):
        return []

    ra_vals = ra_vals[valid]
    dec_vals = dec_vals[valid]
    parallax_vals = parallax_vals[valid]
    poe_vals = poe_vals[valid]
    bp_rp_vals = bp_rp_vals[valid]
    gmag_vals = gmag_vals[valid]
    source_ids = np.array(source_ids, dtype=object)[valid]

    distance_pc = 1000.0 / parallax_vals
    distance_kpc = distance_pc / 1000.0

    abs_mag_g = gmag_vals + 5.0 * np.log10(parallax_vals) - 10.0

    young = abs_mag_g < MAX_ABS_MAG_G

    if not np.any(young):
        return []

    ra_vals = ra_vals[young]
    dec_vals = dec_vals[young]
    parallax_vals = parallax_vals[young]
    poe_vals = poe_vals[young]
    bp_rp_vals = bp_rp_vals[young]
    gmag_vals = gmag_vals[young]
    source_ids = source_ids[young]
    distance_pc = distance_pc[young]
    abs_mag_g = abs_mag_g[young]

    ra_rad = np.deg2rad(ra_vals)
    dec_rad = np.deg2rad(dec_vals)

    cos_dec = np.cos(dec_rad)

    x_eq = cos_dec * np.cos(ra_rad)
    y_eq = cos_dec * np.sin(ra_rad)
    z_eq = np.sin(dec_rad)

    eq_vec = np.column_stack((x_eq, y_eq, z_eq))
    gal_vec = eq_vec @ EQ_TO_GAL.T

    x_helio = (distance_pc / 1000.0) * gal_vec[:, 0]
    y_helio = (distance_pc / 1000.0) * gal_vec[:, 1]
    z_helio = (distance_pc / 1000.0) * gal_vec[:, 2]

    X = SUN_DISTANCE_KPC - x_helio
    Y = y_helio
    Z = z_helio + SUN_HEIGHT_KPC

    docs = []

    for i in range(len(source_ids)):
        docs.append({
            "source_id": int(source_ids[i]),
            "X": float(X[i]),
            "Y": float(Y[i]),
            "Z": float(Z[i]),
            "bp_rp": float(bp_rp_vals[i]),
            "absolute_mag_g": float(abs_mag_g[i])
        })

    return docs

# ==========================================================
# MAIN
# ==========================================================

print("=== ETL MAPA VIA LACTEA (BASE) ===")

t0 = time.time()

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

source = db[SOURCE_COLLECTION]
target = db[TARGET_COLLECTION]

target.drop()

cursor = source.find(
    {},
    {
        "_id": 0,
        FIELD_SOURCE_ID: 1,
        FIELD_RA: 1,
        FIELD_DEC: 1,
        FIELD_PARALLAX: 1,
        FIELD_PARALLAX_OVER_ERROR: 1,
        FIELD_BP_RP: 1,
        FIELD_GMAG: 1
    },
    batch_size=200_000
)

read_block = []
write_ops = []

leidos = 0
insertados = 0

for doc in cursor:
    read_block.append(doc)
    leidos += 1

    if len(read_block) >= READ_BLOCK_SIZE:
        docs = process_block(read_block)

        write_ops.extend(InsertOne(d) for d in docs)
        read_block.clear()

        if len(write_ops) >= WRITE_BATCH_SIZE:
            res = target.bulk_write(write_ops, ordered=False)
            insertados += res.inserted_count
            write_ops.clear()

    if leidos % PRINT_STEP == 0:
        dt = time.time() - t0
        print(f"Leídos: {leidos:,} | Insertados: {insertados:,} | Vel: {leidos/dt:,.0f}/s")

# flush final
if read_block:
    docs = process_block(read_block)
    write_ops.extend(InsertOne(d) for d in docs)

if write_ops:
    res = target.bulk_write(write_ops, ordered=False)
    insertados += res.inserted_count

cursor.close()

t1 = time.time()

print("=================================")
print(f"Leídos: {leidos:,}")
print(f"Insertados: {insertados:,}")
print(f"Tiempo: {(t1-t0)/60:.2f} min")
print("=================================")