import os
import gzip
import csv
import time
import json
import multiprocessing
import numpy as np

from pymongo import MongoClient, WriteConcern
from pymongo.errors import BulkWriteError
from concurrent.futures import ProcessPoolExecutor


ORIGEN = r'C:\Catalogo Gaia\DR3\gaia_source'
DB_NAME = 'TFM'
COLLECTION_NAME = 'Gaia DR3'

BATCH_SIZE = 200000
MAX_WORKERS = 8

FAILED_FILES_JSON = "failed_files.json"

DELTA_T = -16.0  # años (2016 → 2000)
MAS_TO_DEG = 1.0 / 3600000.0


LONG_FIELDS = {"solution_id", "source_id"}

INT_FIELDS = {
    "random_index","ref_epoch",
    "astrometric_n_obs_al","astrometric_n_obs_ac",
    "astrometric_n_good_obs_al","astrometric_n_bad_obs_al",
    "astrometric_params_solved","astrometric_matched_transits",
    "visibility_periods_used","matched_transits",
    "new_matched_transits","matched_transits_removed",
    "phot_g_n_obs","phot_bp_n_obs","phot_rp_n_obs",
    "phot_bp_n_contaminated_transits","phot_bp_n_blended_transits",
    "phot_rp_n_contaminated_transits","phot_rp_n_blended_transits",
    "phot_proc_mode","non_single_star"
}

BOOL_FIELDS = {
    "astrometric_primary_flag","duplicated_source",
    "in_qso_candidates","in_galaxy_candidates",
    "has_xp_continuous","has_xp_sampled","has_rvs",
    "has_epoch_photometry","has_epoch_rv",
    "has_mcmc_gspphot","has_mcmc_msc","in_andromeda_survey"
}

STRING_FIELDS = {
    "designation","phot_variable_flag","libname_gspphot"
}


def convert_field(field, value):
    if value in ("null", "", None):
        return None

    if field in LONG_FIELDS:
        return int(float(value))

    if field in INT_FIELDS:
        return int(float(value))

    if field in BOOL_FIELDS:
        return str(value).lower() == "true"

    if field in STRING_FIELDS:
        return str(value)

    return float(value)


# ===============================
# J2000 APROXIMACIÓN LINEAL
# ===============================

def compute_j2000_batch(docs):

    valid_idx = []
    ra_list = []
    dec_list = []
    pmra_list = []
    pmdec_list = []

    for i, d in enumerate(docs):
        if (
            d.get("ra") is not None and
            d.get("dec") is not None and
            d.get("pmra") is not None and
            d.get("pmdec") is not None
        ):
            valid_idx.append(i)
            ra_list.append(d["ra"])
            dec_list.append(d["dec"])
            pmra_list.append(d["pmra"])
            pmdec_list.append(d["pmdec"])

    if not valid_idx:
        return docs

    ra = np.array(ra_list)
    dec = np.array(dec_list)
    pmra = np.array(pmra_list)
    pmdec = np.array(pmdec_list)

    cos_dec = np.cos(np.deg2rad(dec))

    # Evitar división por cero
    cos_dec[cos_dec == 0] = 1e-12

    ra_j2000 = ra + (DELTA_T * pmra * MAS_TO_DEG) / cos_dec
    dec_j2000 = dec + (DELTA_T * pmdec * MAS_TO_DEG)

    # Normalizar RA 0–360
    ra_j2000 = np.mod(ra_j2000, 360.0)

    for idx, r_new, d_new in zip(valid_idx, ra_j2000, dec_j2000):
        docs[idx]["ra_J2000"] = float(r_new)
        docs[idx]["dec_J2000"] = float(d_new)

    return docs


# ===============================
# PROCESAMIENTO
# ===============================

def procesar_archivo(args):

    archivo, global_inserted, global_discarded, lock, start_time = args

    try:
        client = MongoClient(
            "mongodb://localhost:27017/?w=1&journal=false",
            maxPoolSize=100,
            socketTimeoutMS=0
        )

        db = client[DB_NAME]
        collection = db.get_collection(
            COLLECTION_NAME,
            write_concern=WriteConcern(w=1, j=False)
        )

        ruta = os.path.join(ORIGEN, archivo)

        print(f"[PID {os.getpid()}] >>> INICIO {archivo}")

        local_inserted = 0
        local_discarded = 0
        batch = []

        with gzip.open(ruta, "rt") as f:

            for _ in range(1000):
                next(f)

            reader = csv.DictReader(f)

            for row in reader:

                try:
                    doc = {}
                    for field, value in row.items():
                        if field is None:
                            continue
                        doc[field] = convert_field(field, value)

                    batch.append(doc)

                except Exception:
                    local_discarded += 1
                    continue

                if len(batch) >= BATCH_SIZE:

                    batch = compute_j2000_batch(batch)

                    try:
                        collection.insert_many(
                            batch,
                            ordered=False,
                            bypass_document_validation=True
                        )
                        inserted_now = len(batch)

                    except BulkWriteError as bwe:
                        inserted_now = bwe.details.get("nInserted", 0)
                        errors = len(bwe.details.get("writeErrors", []))
                        local_discarded += errors

                    local_inserted += inserted_now

                    with lock:
                        global_inserted.value += inserted_now
                        global_discarded.value += local_discarded

                        elapsed = time.time() - start_time
                        speed = global_inserted.value / elapsed if elapsed > 0 else 0

                        print(
                            f"[GLOBAL] Insertados: {global_inserted.value:,} | "
                            f"Descartados: {global_discarded.value:,} | "
                            f"{speed:,.0f} reg/s"
                        )

                    batch = []
                    local_discarded = 0

            if batch:

                batch = compute_j2000_batch(batch)

                try:
                    collection.insert_many(
                        batch,
                        ordered=False,
                        bypass_document_validation=True
                    )
                    inserted_now = len(batch)

                except BulkWriteError as bwe:
                    inserted_now = bwe.details.get("nInserted", 0)
                    errors = len(bwe.details.get("writeErrors", []))
                    local_discarded += errors

                local_inserted += inserted_now

                with lock:
                    global_inserted.value += inserted_now
                    global_discarded.value += local_discarded

        print(f"[{archivo}] FINAL → Insertados: {local_inserted:,}")
        return {"archivo": archivo, "status": "ok"}

    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN FICHERO] {archivo}")
        print(str(e))
        return {"archivo": archivo, "status": "failed", "error": str(e)}


if __name__ == "__main__":

    print("\n=============================================")
    print("   GAIA DR3 INGEST ENGINE + J2000 (LINEAR)")
    print("=============================================")

    client = MongoClient("mongodb://localhost:27017/")
    collection = client[DB_NAME][COLLECTION_NAME]

    collection.drop()

    if os.path.exists(FAILED_FILES_JSON):
        os.remove(FAILED_FILES_JSON)

    manager = multiprocessing.Manager()
    global_inserted = manager.Value('i', 0)
    global_discarded = manager.Value('i', 0)
    lock = manager.Lock()

    archivos = sorted([f for f in os.listdir(ORIGEN) if f.endswith(".gz")])

    start_time = time.time()

    args = [
        (archivo, global_inserted, global_discarded, lock, start_time)
        for archivo in archivos
    ]

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        resultados = list(executor.map(procesar_archivo, args))

    failed_files = [r for r in resultados if r["status"] == "failed"]

    if failed_files:
        with open(FAILED_FILES_JSON, "w", encoding="utf-8") as jf:
            json.dump(failed_files, jf, indent=4)

    print("\n=============================================")
    print(f"TOTAL INSERTADO: {global_inserted.value:,}")
    print(f"TOTAL DESCARTADO: {global_discarded.value:,}")
    print(f"TIEMPO TOTAL: {(time.time()-start_time)/3600:.2f} horas")
    print("=============================================\n")