#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
F4:P2 – 6D Espacio Físico Completo (INSERT ONLY, sin reanudar)

Objetivo:
- Construir desde cero la colección destino con SOLO fuentes 6D reales.
- Máxima precisión: Astropy (SkyCoord -> Galactocentric).
- Máximo rendimiento en HDD: INSERT masivo (sin upsert, sin resume).

Requisitos físicos:
- parallax > 0
- pmra, pmdec presentes
- radial_velocity real (no None)
- parallax_over_error > 5
- ruwe < 1.4

Incluye:
- Sesión explícita Mongo (evita timeout real)
- Projection para reducir I/O BSON
- batch_size del cursor
- bulk_insert estable con logs
"""

import time
import numpy as np
from pymongo import MongoClient, InsertOne
from astropy.coordinates import SkyCoord, Galactocentric
import astropy.units as u


# =========================
# CONFIGURACIÓN
# =========================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"
COL_SOURCE = "Gaia_DR3"
COL_DEST = "F4:P2 -> 6D Espacio Físico Completo"

BATCH_SIZE = 5000
CURSOR_BATCH_SIZE = 20000


# =========================
# CONEXIÓN
# =========================

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

source = db[COL_SOURCE]
dest = db[COL_DEST]

print("\n=============================================")
print("   F4:P2 – 6D ESPACIO FÍSICO COMPLETO (INSERT)")
print("=============================================\n")
print(f"Origen : {DB_NAME}.{COL_SOURCE}")
print(f"Destino: {DB_NAME}.{COL_DEST}")
print("Modo   : INSERT ONLY (sin reanudar)\n")


# =========================
# (OPCIONAL) BORRAR DESTINO
# =========================
# Si quieres blindarlo para empezar siempre limpio, descomenta:
# dest.drop()
# print("Destino borrado (drop). Empezando desde cero.\n")


# =========================
# FILTRO 6D FÍSICO REAL
# =========================

query = {
    "parallax": {"$gt": 0},
    "radial_velocity": {"$exists": True, "$ne": None},
    "pmra": {"$exists": True},
    "pmdec": {"$exists": True},
    "parallax_over_error": {"$gt": 5},
    "ruwe": {"$lt": 1.4}
}

# Projection: traer solo lo necesario
projection = {
    "_id": 0,
    "source_id": 1,
    "ra": 1,
    "dec": 1,
    "parallax": 1,
    "pmra": 1,
    "pmdec": 1,
    "radial_velocity": 1
}


# =========================
# PROCESAMIENTO
# =========================

ops = []
processed = 0

start_time = time.time()
last_bulk_time = start_time
last_bulk_processed = 0

with client.start_session() as session:

    cursor = source.find(
        query,
        projection=projection,
        no_cursor_timeout=True,
        session=session
    ).sort("source_id", 1).batch_size(CURSOR_BATCH_SIZE)

    try:
        for doc in cursor:

            try:
                # -------------------------
                # Distancia (kpc)
                # Gaia parallax está en mas:
                # d(pc) ≈ 1000 / parallax(mas)
                # d(kpc) ≈ 1 / parallax(mas)
                # -------------------------
                par = doc["parallax"]
                if par <= 0:
                    continue
                distance_kpc = 1.0 / par

                c = SkyCoord(
                    ra=doc["ra"] * u.deg,
                    dec=doc["dec"] * u.deg,
                    distance=distance_kpc * u.kpc,
                    pm_ra_cosdec=doc["pmra"] * u.mas / u.yr,
                    pm_dec=doc["pmdec"] * u.mas / u.yr,
                    radial_velocity=doc["radial_velocity"] * u.km / u.s,
                    frame="icrs"
                )

                g = c.transform_to(Galactocentric())

                X = g.x.to(u.kpc).value
                Y = g.y.to(u.kpc).value
                Z = g.z.to(u.kpc).value

                VX = g.v_x.to(u.km/u.s).value
                VY = g.v_y.to(u.km/u.s).value
                VZ = g.v_z.to(u.km/u.s).value

                # -------------------------
                # Derivados
                # -------------------------
                r = np.sqrt(X**2 + Y**2 + Z**2)
                v2 = VX**2 + VY**2 + VZ**2
                v = np.sqrt(v2)

                R_cyl = np.sqrt(X**2 + Y**2)
                phi = np.arctan2(Y, X)

                Lx = Y * VZ - Z * VY
                Ly = Z * VX - X * VZ
                Lz = X * VY - Y * VX
                L_perp = np.sqrt(Lx**2 + Ly**2)

                E_proxy = 0.5 * v2

                # -------------------------
                # INSERT ONE (en bulk)
                # -------------------------
                ops.append(
                    InsertOne({
                        "source_id": doc["source_id"],
                        "X": X, "Y": Y, "Z": Z,
                        "VX": VX, "VY": VY, "VZ": VZ,
                        "R_cyl": R_cyl,
                        "phi": phi,
                        "r": r,
                        "v": v,
                        "v2": v2,
                        "Lx": Lx,
                        "Ly": Ly,
                        "Lz": Lz,
                        "L_perp": L_perp,
                        "E_proxy": E_proxy
                    })
                )

                # -------------------------
                # Flush bulk
                # -------------------------
                if len(ops) >= BATCH_SIZE:
                    t0 = time.time()
                    dest.bulk_write(ops, ordered=False)
                    dt = time.time() - t0

                    processed += len(ops)

                    now = time.time()
                    tramo = processed - last_bulk_processed
                    tramo_dt = (now - last_bulk_time) if now > last_bulk_time else 1e-9
                    tramo_rate = tramo / tramo_dt

                    print(
                        f"[bulk] ops={len(ops):,} | bulk={dt:.2f}s | "
                        f"tramo={tramo:,} en {tramo_dt:.2f}s ({tramo_rate:,.0f} reg/s) | "
                        f"total={processed:,}"
                    )

                    last_bulk_time = now
                    last_bulk_processed = processed
                    ops = []

                # -------------------------
                # Log global (cada 100k)
                # -------------------------
                if processed and processed % 100000 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    print(f"Procesados: {processed:,} | media={rate:,.0f} reg/s")

            except Exception as e:
                # Log mínimo y continuar
                print(f"Error en source_id={doc.get('source_id')}: {e}")
                continue

    finally:
        cursor.close()


# Flush final
if ops:
    t0 = time.time()
    dest.bulk_write(ops, ordered=False)
    dt = time.time() - t0
    processed += len(ops)
    print(f"[bulk-final] ops={len(ops):,} | bulk={dt:.2f}s | total={processed:,}")


total_time = time.time() - start_time
print("\n=============================================")
print("FINALIZADO")
print(f"Total procesados: {processed:,}")
print(f"Tiempo total: {total_time/60:.2f} min")
print("=============================================\n")