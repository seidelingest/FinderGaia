#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Búsqueda de estrellas raras en Gaia DR3
Método: rareza por densidad local en el diagrama HR

Estrategia:
- Construir histograma 2D del HR (BP-RP vs M_G)
- Asignar a cada estrella la densidad de su bin
- Rareza = 1 / densidad_bin
- Extraer las más raras

Ventajas:
- Escala bien a millones de estrellas
- Mucho más rápido que KDE global
- Muy adecuado para Gaia DR3
"""

import time
import math
import numpy as np
from pymongo import MongoClient, InsertOne

# =========================================================
# CONFIGURACIÓN
# =========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"

SOURCE_COLLECTION = "F5:P1 -> HR Enriquecido"
TARGET_COLLECTION = "F6:P1 -> Gaia DR3 Objetos Raros HR"

# Número de bins del histograma HR
BINS_X = 500
BINS_Y = 500

# Rango físico del HR
# Ajusta si quieres abrir/cerrar el plano
X_MIN, X_MAX = -1.0, 5.0      # color_bp_rp
Y_MIN, Y_MAX = -5.0, 15.0     # absolute_mag_g

# Cuántos candidatos guardar
TOP_N = 10000

# Tamaño de lote para lectura desde Mongo
BATCH_SIZE = 200_000

# Mostrar progreso cada N estrellas
LOG_EVERY = 1_000_000


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def safe_float(value):
    """
    Convierte a float si es válido.
    Devuelve None si el valor es nulo, NaN, infinito o inválido.
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


def digitize_points(bp, mg, xedges, yedges):
    """
    Asigna cada estrella a un bin del histograma 2D.

    Retorna:
    - x_idx
    - y_idx
    - mask_valid: True si cae dentro del rango del histograma
    """
    x_idx = np.digitize(bp, xedges) - 1
    y_idx = np.digitize(mg, yedges) - 1

    mask_valid = (
        (x_idx >= 0) & (x_idx < len(xedges) - 1) &
        (y_idx >= 0) & (y_idx < len(yedges) - 1)
    )

    return x_idx, y_idx, mask_valid


# =========================================================
# PROGRAMA PRINCIPAL
# =========================================================

def main():
    print("========================================================")
    print(" BÚSQUEDA DE OBJETOS RAROS EN GAIA DR3")
    print(" Método: rareza por densidad local en el HR diagram")
    print("========================================================\n")

    t0 = time.time()

    print("Conectando a MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    source = db[SOURCE_COLLECTION]
    target = db[TARGET_COLLECTION]

    print("Conexión establecida.\n")

    print("Recreando colección destino...")
    target.drop()

    # Índices destino
    target.create_index("source_id")
    target.create_index("rarity_score")
    target.create_index([("color_bp_rp", 1), ("absolute_mag_g", 1)])

    query = {
        "absolute_mag_g": {"$ne": None},
        "color_bp_rp": {"$ne": None}
    }

    projection = {
        "_id": 0,
        "source_id": 1,
        "absolute_mag_g": 1,
        "color_bp_rp": 1,
        "stellar_class": 1,
        "teff_estimated": 1,
        "luminosity_solar": 1,
        "parallax": 1,
        "phot_g_mean_mag": 1
    }

    print("Contando estrellas válidas...")
    total_docs = source.count_documents(query)
    print(f"Total estrellas HR válidas: {total_docs:,}\n")

    if total_docs == 0:
        print("No hay estrellas válidas en la colección.")
        return

    # -----------------------------------------------------
    # PRIMER PASO: LEER DATOS Y CONSTRUIR ARRAYS
    # -----------------------------------------------------

    print("Reservando arrays NumPy...")
    ids = np.empty(total_docs, dtype=np.int64)
    bp = np.empty(total_docs, dtype=np.float64)
    mg = np.empty(total_docs, dtype=np.float64)

    print("Leyendo estrellas desde MongoDB...")
    cursor = source.find(query, projection).batch_size(BATCH_SIZE)

    i = 0
    for doc in cursor:
        ids[i] = int(doc["source_id"])
        bp[i] = float(doc["color_bp_rp"])
        mg[i] = float(doc["absolute_mag_g"])
        i += 1

        if i % LOG_EVERY == 0:
            print(f"Estrellas leídas: {i:,}")

    print(f"\nLectura finalizada. Total cargadas: {i:,}\n")

    # Por seguridad, si hubiera discrepancias
    ids = ids[:i]
    bp = bp[:i]
    mg = mg[:i]

    # -----------------------------------------------------
    # SEGUNDO PASO: CONSTRUIR HISTOGRAMA HR
    # -----------------------------------------------------

    print("Construyendo histograma 2D del diagrama HR...")

    H, xedges, yedges = np.histogram2d(
        bp,
        mg,
        bins=[BINS_X, BINS_Y],
        range=[[X_MIN, X_MAX], [Y_MIN, Y_MAX]]
    )

    print("Histograma HR construido.")
    print(f"Tamaño histograma: {H.shape}\n")

    # -----------------------------------------------------
    # TERCER PASO: ASIGNAR DENSIDAD LOCAL A CADA ESTRELLA
    # -----------------------------------------------------

    print("Asignando densidad local a cada estrella...")

    x_idx, y_idx, mask_valid = digitize_points(bp, mg, xedges, yedges)

    density = np.zeros(bp.shape[0], dtype=np.float64)

    valid_pos = np.where(mask_valid)[0]
    density[valid_pos] = H[x_idx[valid_pos], y_idx[valid_pos]]

    # Evitar divisiones por cero
    density[density <= 0] = 1.0

    # Rareza: inversa de la densidad
    rare_score = 1.0 / density

    print("Rareza calculada.\n")

    # -----------------------------------------------------
    # CUARTO PASO: EXTRAER LOS MÁS RAROS
    # -----------------------------------------------------

    print(f"Seleccionando las {TOP_N:,} estrellas más raras...")

    if TOP_N >= len(rare_score):
        rare_idx = np.argsort(rare_score)[::-1]
    else:
        # Mucho más eficiente que ordenar todo
        rare_idx = np.argpartition(rare_score, -TOP_N)[-TOP_N:]
        rare_idx = rare_idx[np.argsort(rare_score[rare_idx])[::-1]]

    print("Selección completada.\n")

    # -----------------------------------------------------
    # QUINTO PASO: RECUPERAR CAMPOS COMPLETOS SOLO DE LOS TOP
    # -----------------------------------------------------

    print("Preparando escritura en MongoDB...")

    rare_source_ids = ids[rare_idx].tolist()
    rare_score_map = {int(ids[j]): float(rare_score[j]) for j in rare_idx}

    # Leer solo los documentos raros para guardar contexto completo
    rare_cursor = source.find(
        {"source_id": {"$in": rare_source_ids}},
        projection
    )

    operations = []
    recovered = 0

    for doc in rare_cursor:
        sid = int(doc["source_id"])
        doc_out = {
            "source_id": sid,
            "color_bp_rp": safe_float(doc.get("color_bp_rp")),
            "absolute_mag_g": safe_float(doc.get("absolute_mag_g")),
            "stellar_class": doc.get("stellar_class"),
            "teff_estimated": safe_float(doc.get("teff_estimated")),
            "luminosity_solar": safe_float(doc.get("luminosity_solar")),
            "parallax": safe_float(doc.get("parallax")),
            "phot_g_mean_mag": safe_float(doc.get("phot_g_mean_mag")),
            "rarity_score": rare_score_map[sid]
        }
        operations.append(InsertOne(doc_out))
        recovered += 1

    if operations:
        result = target.bulk_write(operations, ordered=False)
        inserted = result.inserted_count
    else:
        inserted = 0

    # Índices adicionales finales
    target.create_index([("rarity_score", -1)])
    target.create_index([("stellar_class", 1), ("rarity_score", -1)])

    # -----------------------------------------------------
    # RESUMEN FINAL
    # -----------------------------------------------------

    elapsed = time.time() - t0

    print("========================================================")
    print(" PROCESO FINALIZADO")
    print("========================================================")
    print(f"Estrellas HR analizadas : {len(ids):,}")
    print(f"Candidatos raros        : {TOP_N:,}")
    print(f"Documentos recuperados  : {recovered:,}")
    print(f"Documentos insertados   : {inserted:,}")
    print(f"Tiempo total            : {elapsed:.2f} s")
    print("========================================================\n")

    print("Top 20 candidatos más raros:\n")

    for rank, j in enumerate(rare_idx[:20], start=1):
        print(
            f"{rank:>2}. "
            f"source_id={int(ids[j])} | "
            f"bp_rp={bp[j]:.4f} | "
            f"M_G={mg[j]:.4f} | "
            f"rarity={rare_score[j]:.8f}"
        )


if __name__ == "__main__":
    main()