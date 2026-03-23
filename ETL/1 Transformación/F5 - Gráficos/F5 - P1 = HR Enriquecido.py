#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
F5 - P1 = F5 - HR Enriquecido (versión optimizada, vectorizada y multihilo)

Objetivo:
- Leer Gaia DR3 desde MongoDB
- Calcular M_G (magnitud absoluta G) cuando no exista
- Clasificar estrellas en el diagrama HR
- Guardar el resultado en una colección enriquecida
- Optimizar el rendimiento para grandes volúmenes de datos

Clases:
- white_dwarf
- red_giant
- subgiant
- main_sequence
- unknown
"""

import time
import math
import os
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

import numpy as np
from pymongo import MongoClient, InsertOne

# =========================================================
# CONFIGURACIÓN
# =========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"

SOURCE_COLLECTION = "Gaia DR3"
TARGET_COLLECTION = "F5:P1 -> F5 - HR Enriquecido"

# Tamaño del lote. Ajusta según RAM disponible y rendimiento del disco.
BATCH_SIZE = 200_000

# Número máximo de lotes pendientes en memoria.
# Evita llenar RAM si el procesamiento va más rápido que la escritura.
MAX_PENDING_BATCHES = 4

# Número de hilos de procesamiento.
# No subas esto sin necesidad. 2-4 suele ser razonable en ETL mixto I/O + NumPy.
# MAX_WORKERS = min(4, max(2, (os.cpu_count() or 4) // 2))
MAX_WORKERS = 20

# Frecuencia de log
LOG_EVERY = 1

# Si quieres conservar registros incompletos como "unknown", deja True.
# Si prefieres solo registros potencialmente clasificables, pon False.
KEEP_UNKNOWN_RECORDS = False


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def safe_float(value):
    """
    Convierte un valor a float si es posible.
    Devuelve None si el valor es nulo, NaN, infinito o no convertible.
    """
    if value is None:
        return None
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def compute_absolute_mag_g_vectorized(phot_g_array, parallax_array):
    """
    Calcula magnitud absoluta G vectorizada.

    Fórmula:
        M_G = G + 5*log10(parallax_mas) - 10

    Requisitos:
    - phot_g_mean_mag no NaN
    - parallax > 0

    Parámetros
    ----------
    phot_g_array : np.ndarray
    parallax_array : np.ndarray

    Retorna
    -------
    np.ndarray
        Array con M_G calculada o NaN si no es calculable.
    """
    abs_mag = np.full(phot_g_array.shape[0], np.nan, dtype=np.float64)

    valid = (
        ~np.isnan(phot_g_array) &
        ~np.isnan(parallax_array) &
        (parallax_array > 0.0)
    )

    if np.any(valid):
        abs_mag[valid] = phot_g_array[valid] + 5.0 * np.log10(parallax_array[valid]) - 10.0

    return abs_mag


def classify_vectorized(bp_rp_array, abs_mag_array):
    """
    Clasificación HR vectorizada.

    Reglas aproximadas:
    - white_dwarf: M_G > 10 + 2.5 * (BP-RP)
    - red_giant:   M_G < 2.5 + 1.5 * (BP-RP)
    - subgiant:    2.5 + 1.5*(BP-RP) <= M_G < 4 + 2*(BP-RP)
    - main_sequence: resto
    - unknown: faltan datos

    Parámetros
    ----------
    bp_rp_array : np.ndarray
    abs_mag_array : np.ndarray

    Retorna
    -------
    np.ndarray[str]
    """
    n = len(bp_rp_array)
    result = np.full(n, "unknown", dtype=object)

    valid = ~np.isnan(bp_rp_array) & ~np.isnan(abs_mag_array)

    if not np.any(valid):
        return result

    bp = bp_rp_array[valid]
    mg = abs_mag_array[valid]

    valid_result = np.full(bp.shape[0], "main_sequence", dtype=object)

    # White dwarfs
    cond_white = mg > (10.0 + 2.5 * bp)
    valid_result[cond_white] = "white_dwarf"

    # Red giants
    cond_giant = mg < (2.5 + 1.5 * bp)
    valid_result[cond_giant] = "red_giant"

    # Subgiants
    cond_sub = (
        (mg >= (2.5 + 1.5 * bp)) &
        (mg <  (4.0 + 2.0 * bp))
    )
    cond_sub_final = cond_sub & (~cond_white) & (~cond_giant)
    valid_result[cond_sub_final] = "subgiant"

    result[valid] = valid_result
    return result


def chunked_cursor(cursor, batch_size):
    """
    Agrupa documentos del cursor en lotes.
    """
    batch = []
    for doc in cursor:
        batch.append(doc)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


# =========================================================
# PROCESAMIENTO DE UN LOTE (SE EJECUTA EN HILO)
# =========================================================

def process_batch(batch_docs):
    """
    Procesa un lote completo:
    - convierte campos a arrays NumPy
    - calcula M_G si falta
    - clasifica HR
    - devuelve operaciones InsertOne ya preparadas

    Esta función está diseñada para ejecutarse en un hilo worker.
    """
    size = len(batch_docs)

    # Arrays base
    source_ids = np.empty(size, dtype=np.int64)
    bp_rp = np.full(size, np.nan, dtype=np.float64)
    abs_mag_existing = np.full(size, np.nan, dtype=np.float64)
    abs_mag_final = np.full(size, np.nan, dtype=np.float64)
    teff = np.full(size, np.nan, dtype=np.float64)
    luminosity = np.full(size, np.nan, dtype=np.float64)
    parallax = np.full(size, np.nan, dtype=np.float64)
    phot_g = np.full(size, np.nan, dtype=np.float64)

    # Carga de datos del lote
    for i, doc in enumerate(batch_docs):
        sid = doc.get("source_id")
        source_ids[i] = int(sid) if sid is not None else -1

        v = safe_float(doc.get("bp_rp"))
        if v is not None:
            bp_rp[i] = v

        v = safe_float(doc.get("absolute_mag_g"))
        if v is not None:
            abs_mag_existing[i] = v

        v = safe_float(doc.get("teff_gspphot"))
        if v is not None:
            teff[i] = v

        v = safe_float(doc.get("luminosity"))
        if v is not None:
            luminosity[i] = v

        v = safe_float(doc.get("parallax"))
        if v is not None:
            parallax[i] = v

        v = safe_float(doc.get("phot_g_mean_mag"))
        if v is not None:
            phot_g[i] = v

    # Calculamos M_G donde falte y sea posible
    abs_mag_computed = compute_absolute_mag_g_vectorized(phot_g, parallax)

    # Si ya existía absolute_mag_g, lo respetamos.
    # Si no existía, usamos el calculado.
    mask_existing = ~np.isnan(abs_mag_existing)
    abs_mag_final[mask_existing] = abs_mag_existing[mask_existing]

    mask_missing = np.isnan(abs_mag_existing)
    abs_mag_final[mask_missing] = abs_mag_computed[mask_missing]

    # Clasificación HR
    classes = classify_vectorized(bp_rp, abs_mag_final)

    # Métricas del lote
    unknown_count = int(np.sum(classes == "unknown"))
    computed_abs_mag_count = int(np.sum(np.isnan(abs_mag_existing) & ~np.isnan(abs_mag_final)))

    # Preparar escrituras
    operations = []

    for i in range(size):
        stellar_class = str(classes[i])

        # Si no queremos conservar unknown, aquí se descartan
        if (not KEEP_UNKNOWN_RECORDS) and stellar_class == "unknown":
            continue

        doc_out = {
            "source_id": int(source_ids[i]),
            "absolute_mag_g": None if np.isnan(abs_mag_final[i]) else float(abs_mag_final[i]),
            "color_bp_rp": None if np.isnan(bp_rp[i]) else float(bp_rp[i]),
            "teff_estimated": None if np.isnan(teff[i]) else float(teff[i]),
            "luminosity_solar": None if np.isnan(luminosity[i]) else float(luminosity[i]),
            "parallax": None if np.isnan(parallax[i]) else float(parallax[i]),
            "phot_g_mean_mag": None if np.isnan(phot_g[i]) else float(phot_g[i]),
            "stellar_class": stellar_class
        }
        operations.append(InsertOne(doc_out))

    return {
        "batch_size": size,
        "operations": operations,
        "unknown_count": unknown_count,
        "computed_abs_mag_count": computed_abs_mag_count
    }


# =========================================================
# ETL PRINCIPAL
# =========================================================

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    source = db[SOURCE_COLLECTION]
    target = db[TARGET_COLLECTION]

    print("Iniciando clasificación HR vectorizada y multihilo...\n")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Batch size: {BATCH_SIZE:,}")
    print(f"Max pending batches: {MAX_PENDING_BATCHES}\n")

    start_global = time.time()

    # Eliminar colección destino si existe
    if TARGET_COLLECTION in db.list_collection_names():
        print(f"Eliminando colección previa: {TARGET_COLLECTION}")
        target.drop()

    # Índices básicos iniciales
    target.create_index("source_id", unique=False)
    target.create_index("stellar_class")

    projection = {
        "_id": 0,
        "source_id": 1,
        "bp_rp": 1,
        "absolute_mag_g": 1,
        "teff_gspphot": 1,
        "luminosity": 1,
        "parallax": 1,
        "phot_g_mean_mag": 1
    }

    # Query:
    # - si quieres conservar unknown, basta con traer los que tengan algo de interés
    # - si quieres máxima velocidad y menos unknown, endurece el filtro
    if KEEP_UNKNOWN_RECORDS:
        query = {
            "$or": [
                {"bp_rp": {"$ne": None}},
                {"absolute_mag_g": {"$ne": None}},
                {"phot_g_mean_mag": {"$ne": None}},
                {"parallax": {"$ne": None}}
            ]
        }
    else:
        query = {
            "bp_rp": {"$ne": None},
            "phot_g_mean_mag": {"$ne": None},
            "parallax": {"$gt": 0}
        }

    processed = 0
    inserted = 0
    unknown_count = 0
    computed_abs_mag_total = 0
    batch_number = 0

    session = client.start_session()

    try:
        cursor = source.find(
            query,
            projection,
            no_cursor_timeout=True,
            session=session
        ).batch_size(BATCH_SIZE)

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                pending = set()

                for docs in chunked_cursor(cursor, BATCH_SIZE):
                    batch_number += 1

                    # Si hay demasiados lotes pendientes, esperamos a que termine al menos uno
                    while len(pending) >= MAX_PENDING_BATCHES:
                        done, pending = wait(pending, return_when=FIRST_COMPLETED)
                        for future in done:
                            result = future.result()

                            if result["operations"]:
                                wr = target.bulk_write(result["operations"], ordered=False)
                                inserted += wr.inserted_count

                            processed += result["batch_size"]
                            unknown_count += result["unknown_count"]
                            computed_abs_mag_total += result["computed_abs_mag_count"]

                            elapsed_global = time.time() - start_global
                            global_rate = processed / elapsed_global if elapsed_global > 0 else 0.0

                            if batch_number % LOG_EVERY == 0:
                                print(
                                    f"Lotes lanzados: {batch_number:,} | "
                                    f"Procesadas: {processed:,} | "
                                    f"Insertadas: {inserted:,} | "
                                    f"Unknown: {unknown_count:,} | "
                                    f"M_G calculadas: {computed_abs_mag_total:,} | "
                                    f"Velocidad global: {global_rate:,.0f} reg/s"
                                )

                    pending.add(executor.submit(process_batch, docs))

                # Vaciar pendientes al final
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        result = future.result()

                        if result["operations"]:
                            wr = target.bulk_write(result["operations"], ordered=False)
                            inserted += wr.inserted_count

                        processed += result["batch_size"]
                        unknown_count += result["unknown_count"]
                        computed_abs_mag_total += result["computed_abs_mag_count"]

                        elapsed_global = time.time() - start_global
                        global_rate = processed / elapsed_global if elapsed_global > 0 else 0.0

                        print(
                            f"Lotes completados | "
                            f"Procesadas: {processed:,} | "
                            f"Insertadas: {inserted:,} | "
                            f"Unknown: {unknown_count:,} | "
                            f"M_G calculadas: {computed_abs_mag_total:,} | "
                            f"Velocidad global: {global_rate:,.0f} reg/s"
                        )

        finally:
            cursor.close()

    finally:
        session.end_session()

    total_time = time.time() - start_global

    print("\nFinalizado")
    print(f"Total procesadas   : {processed:,}")
    print(f"Total insertadas   : {inserted:,}")
    print(f"Total unknown      : {unknown_count:,}")
    print(f"Total M_G calculada: {computed_abs_mag_total:,}")
    print(f"Tiempo total       : {total_time:.2f} s")
    print(f"Velocidad media    : {processed / total_time:,.0f} reg/s")

    # Índices finales recomendables
    print("\nCreando índices finales...")
    target.create_index("source_id", unique=False)
    target.create_index([("stellar_class", 1), ("color_bp_rp", 1)])
    target.create_index([("stellar_class", 1), ("absolute_mag_g", 1)])
    target.create_index([("color_bp_rp", 1), ("absolute_mag_g", 1)])
    print("Índices creados.")


# =========================================================
# ENTRADA
# =========================================================

if __name__ == "__main__":
    main()