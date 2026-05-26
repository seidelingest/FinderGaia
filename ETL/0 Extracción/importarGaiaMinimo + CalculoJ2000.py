# ==========================================================
# IMPORTADOR GAIA DR3 OPTIMIZADO + COORDENADAS J2000
# - Sin descompresión a disco
# - Streaming directo desde .gz
# - Solo columnas necesarias
# - Inserción por bloques
# - Calcula RA_J2000 / DEC_J2000
# ==========================================================

import os
import gzip
import pandas as pd
import numpy as np
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor

# =========================
# CONFIG
# =========================

DIRECTORIO = r'G:\CatalogoGaia\GaiaDR3'
DB_NAME = 'TFM'
COLLECTION_NAME = 'Gaia DR3'

CHUNK_SIZE = 50000
MAX_WORKERS = 12

# =========================
# CONSTANTES J2000
# =========================

DELTA_T = -16.0                 # Gaia ref_epoch 2016 -> J2000
MAS_TO_DEG = 1.0 / 3600000.0

# =========================
# CAMPOS OBJETIVO
# =========================

COLUMNAS_OBJETIVO = [
    "source_id",
    "ra",
    "dec",
    "pmra",
    "pmdec",
    "has_xp_sampled",
    "bp_rp",
    "phot_g_mean_mag",
    "teff_gspphot",
    "phot_bp_mean_mag",
    "phot_rp_mean_mag",
    "distance_gspphot",
    "classprob_dsc_combmod_quasar",
    "classprob_dsc_combmod_galaxy",
    "classprob_dsc_combmod_star",
    "parallax",
    "matched_transits"
]

# =========================
# MONGO
# =========================

client = MongoClient("mongodb://localhost:27017/")
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

print("🗑️ Borrando colección...")
collection.delete_many({})

# =========================
# DETECTAR CABECERA REAL
# =========================

def encontrar_skiprows(ruta_gz):
    with gzip.open(ruta_gz, 'rt', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if line.startswith("solution_id"):
                return i
    return None

# =========================
# CALCULAR J2000
# =========================

def calcular_j2000(chunk):

    if not {"ra", "dec", "pmra", "pmdec"}.issubset(chunk.columns):
        return chunk

    validos = (
        chunk["ra"].notna() &
        chunk["dec"].notna() &
        chunk["pmra"].notna() &
        chunk["pmdec"].notna()
    )

    if validos.sum() == 0:
        chunk["ra_J2000"] = np.nan
        chunk["dec_J2000"] = np.nan
        return chunk

    ra = chunk.loc[validos, "ra"].astype(float).values
    dec = chunk.loc[validos, "dec"].astype(float).values
    pmra = chunk.loc[validos, "pmra"].astype(float).values
    pmdec = chunk.loc[validos, "pmdec"].astype(float).values

    cos_dec = np.cos(np.deg2rad(dec))
    cos_dec[cos_dec == 0] = 1e-12

    ra_j2000 = ra + (DELTA_T * pmra * MAS_TO_DEG) / cos_dec
    dec_j2000 = dec + (DELTA_T * pmdec * MAS_TO_DEG)

    ra_j2000 = np.mod(ra_j2000, 360.0)

    chunk["ra_J2000"] = np.nan
    chunk["dec_J2000"] = np.nan

    chunk.loc[validos, "ra_J2000"] = ra_j2000
    chunk.loc[validos, "dec_J2000"] = dec_j2000

    return chunk

# =========================
# PROCESADO
# =========================

def procesar_archivo(nombre):

    ruta = os.path.join(DIRECTORIO, nombre)
    print(f"🚀 {nombre}")

    try:
        skiprows = encontrar_skiprows(ruta)

        if skiprows is None:
            print(f"❌ No se encontró cabecera en {nombre}")
            return

        print(f"🔍 skiprows={skiprows}")

        total = 0

        with gzip.open(ruta, 'rt', encoding='utf-8') as f:

            reader = pd.read_csv(
                f,
                skiprows=skiprows,
                chunksize=CHUNK_SIZE,
                low_memory=False
            )

            for chunk in reader:

                cols = [c for c in COLUMNAS_OBJETIVO if c in chunk.columns]
                chunk = chunk[cols]

                # Calcular coordenadas J2000
                chunk = calcular_j2000(chunk)

                docs = chunk.to_dict("records")

                if docs:
                    collection.insert_many(docs, ordered=False)
                    total += len(docs)

                    print(f"{nombre} -> {total:,}")

        print(f"✅ Finalizado {nombre}")

    except Exception as e:
        print(f"❌ Error en {nombre}: {e}")

# =========================
# EJECUCIÓN
# =========================

archivos = [f for f in os.listdir(DIRECTORIO) if f.endswith(".gz")]

print(f"📦 Total archivos: {len(archivos)}")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    executor.map(procesar_archivo, archivos)

print("🏁 IMPORTACIÓN COMPLETADA")