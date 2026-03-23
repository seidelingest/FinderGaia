import numpy as np
import time
from pymongo import MongoClient
from itertools import islice

# ==========================
# CONFIGURACIÓN
# ==========================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"

# OJO: en tu P2 usas "Gaia_DR3". Aquí tenías "Gaia DR3".
# Asegúrate de que esta es la colección REAL.
SOURCE_COLLECTION = "Gaia DR3"

TARGET_COLLECTION = "F4:P1 -> Gaia DR3 Galactocentric"

BATCH_SIZE = 200000
DELTA_T = -16.0
K = 4.74047
KM_S_TO_PC_YR = 1.022712e-6

# ==========================
# CONEXIÓN
# ==========================

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
source = db[SOURCE_COLLECTION]
target = db[TARGET_COLLECTION]

if TARGET_COLLECTION in db.list_collection_names():
    print("Eliminando colección destino previa...")
    db[TARGET_COLLECTION].drop()

print("Iniciando ETL 3D vectorizado (proyección mínima) + source_id...\n")

start_time = time.time()
processed = 0
calculated = 0
batch_number = 0

session = client.start_session()

# ✅ CORRECCIÓN: incluir source_id en la proyección
projection = {
    "_id": 0,          # si no quieres arrastrar ObjectId del origen
    "source_id": 1,    # ✅ CLAVE
    "ra": 1,
    "dec": 1,
    "parallax": 1,
    "pmra": 1,
    "pmdec": 1,
    "radial_velocity": 1
}

cursor = source.find(
    {},
    projection,
    no_cursor_timeout=True,
    session=session
).batch_size(BATCH_SIZE)

try:
    while True:
        batch_start = time.time()
        stars = list(islice(cursor, BATCH_SIZE))
        if not stars:
            break

        # Arrays para vectorización SOLO de los válidos
        ra, dec, parallax, pmra, pmdec, rv = [], [], [], [], [], []
        valid_mask = []

        for s in stars:
            # ✅ CORRECCIÓN: validar también source_id
            sid = s.get("source_id")

            r = s.get("ra")
            d = s.get("dec")
            p = s.get("parallax")
            mra = s.get("pmra")
            mdec = s.get("pmdec")
            vr = s.get("radial_velocity", 0.0)

            if sid is None or None in (r, d, p, mra, mdec) or p is None or p <= 0:
                valid_mask.append(False)
            else:
                valid_mask.append(True)
                ra.append(r)
                dec.append(d)
                parallax.append(p)
                pmra.append(mra)
                pmdec.append(mdec)
                rv.append(vr if vr is not None else 0.0)

        # Aunque no haya ninguno válido, igual insertamos el batch (con CalculatedJ2000=false)
        any_valid = any(valid_mask)

        if any_valid:
            # Vectorización
            ra = np.deg2rad(np.array(ra, dtype=np.float64))
            dec = np.deg2rad(np.array(dec, dtype=np.float64))
            parallax = np.array(parallax, dtype=np.float64)
            pmra = np.array(pmra, dtype=np.float64)
            pmdec = np.array(pmdec, dtype=np.float64)
            rv = np.array(rv, dtype=np.float64)

            d_pc = 1000.0 / parallax

            cosd = np.cos(dec)
            sind = np.sin(dec)
            cosa = np.cos(ra)
            sina = np.sin(ra)

            x = d_pc * cosd * cosa
            y = d_pc * cosd * sina
            z = d_pc * sind

            mu_ra = pmra / 1000.0
            mu_dec = pmdec / 1000.0

            v_ra = K * mu_ra * d_pc
            v_dec = K * mu_dec * d_pc

            e_ra_x = -sina
            e_ra_y = cosa
            e_dec_x = -cosa * sind
            e_dec_y = -sina * sind
            e_dec_z = cosd

            e_r_x = x / d_pc
            e_r_y = y / d_pc
            e_r_z = z / d_pc

            vx = (v_ra * e_ra_x + v_dec * e_dec_x + rv * e_r_x) * KM_S_TO_PC_YR
            vy = (v_ra * e_ra_y + v_dec * e_dec_y + rv * e_r_y) * KM_S_TO_PC_YR
            vz = (v_dec * e_dec_z + rv * e_r_z) * KM_S_TO_PC_YR

            x2 = x + vx * DELTA_T
            y2 = y + vy * DELTA_T
            z2 = z + vz * DELTA_T

            rr = np.sqrt(x2**2 + y2**2 + z2**2)
            dec2 = np.rad2deg(np.arcsin(z2 / rr))
            ra2 = np.rad2deg(np.arctan2(y2, x2)) % 360.0

        # Reconstrucción: construir docs de salida homogéneos (no mutar "stars" in-place)
        new_docs = []
        calc_index = 0

        for i in range(len(stars)):
            s = stars[i]

            out = {
                # ✅ CLAVE: mantener source_id SIEMPRE
                "source_id": s.get("source_id"),

                # Campos base (útiles para consultas/crossmatch)
                "ra": s.get("ra"),
                "dec": s.get("dec"),
                "parallax": s.get("parallax"),
                "pmra": s.get("pmra"),
                "pmdec": s.get("pmdec"),
                "radial_velocity": s.get("radial_velocity", None),
            }

            if valid_mask[i]:
                out["ra_J2000"] = float(ra2[calc_index])
                out["dec_J2000"] = float(dec2[calc_index])
                out["CalculatedJ2000"] = True
                calc_index += 1
                calculated += 1
            else:
                out["CalculatedJ2000"] = False

            new_docs.append(out)

        # INSERT masivo
        target.insert_many(new_docs, ordered=False)

        batch_number += 1
        processed += len(new_docs)

        batch_elapsed = time.time() - batch_start
        total_elapsed = time.time() - start_time

        batch_rate = len(new_docs) / batch_elapsed if batch_elapsed > 0 else 0
        avg_rate = processed / total_elapsed if total_elapsed > 0 else 0
        valid_percent = (calculated / processed) * 100 if processed > 0 else 0

        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"Leídos: {processed:,} | "
            f"Calculados: {calculated:,} ({valid_percent:.2f}%) | "
            f"Batch: {batch_rate:,.0f} r/s | "
            f"Media: {avg_rate:,.0f} r/s"
        )

finally:
    cursor.close()
    session.end_session()

total_time = time.time() - start_time

print("\nETL COMPLETADO")
print(f"Total leídos: {processed:,}")
print(f"Tiempo total: {total_time/3600:.2f} h")
print(f"Velocidad media final: {processed/total_time:,.0f} reg/s")

# ==========================
# ÍNDICES (DESPUÉS DEL ETL)
# ==========================
# Cuando termine, crea al menos:
# db.getCollection("F4:P1 -> Gaia DR3 Galactocentric").createIndex({ source_id: 1 }, { unique: true })