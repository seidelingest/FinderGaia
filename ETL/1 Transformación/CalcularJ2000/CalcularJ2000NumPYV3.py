import os
import gzip
import csv
import time
import numpy as np
import multiprocessing
from datetime import datetime
from pymongo import MongoClient, WriteConcern
from concurrent.futures import ProcessPoolExecutor

# ==========================================
# CONFIGURACIÓN
# ==========================================

ORIGEN = r'C:\Catalogo Gaia\DR3\gaia_source'

DB_NAME = "TFM"
COLLECTION_NAME = "Gaia_DR3"

TOTAL_REGISTROS = 1_812_000_000

BATCH_SIZE = 300000
MAX_WORKERS = 2

DELTA_T = -16.0
K = 4.74047
KM_S_TO_PC_YR = 1.022712e-6
PARALLAX_THRESHOLD = 0.05

# ==========================================
# TIPADO ESTRICTO
# ==========================================

LONG_FIELDS = {"solution_id", "source_id"}

INT_FIELDS = {
    "random_index","ref_epoch",
    "astrometric_n_obs_al","astrometric_n_obs_ac",
    "astrometric_n_good_obs_al","astrometric_n_bad_obs_al",
    "astrometric_params_solved","astrometric_matched_transits",
    "visibility_periods_used","matched_transits",
    "new_matched_transits","matched_transits_removed",
    "phot_g_n_obs","phot_bp_n_obs","phot_rp_n_obs",
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

# ==========================================
# CÁLCULO J2000
# ==========================================

def calcular_j2000(doc):

    ra = doc.get("ra")
    dec = doc.get("dec")
    parallax = doc.get("parallax")
    pmra = doc.get("pmra")
    pmdec = doc.get("pmdec")
    rv = doc.get("radial_velocity") or 0.0

    if None in (ra, dec, pmra, pmdec) or parallax is None or parallax <= 0:
        doc["CalculatedJ2000"] = False
        return doc

    try:

        if parallax >= PARALLAX_THRESHOLD:

            ra_rad = np.deg2rad(ra)
            dec_rad = np.deg2rad(dec)

            d_pc = 1000.0 / parallax

            cosd = np.cos(dec_rad)
            sind = np.sin(dec_rad)
            cosa = np.cos(ra_rad)
            sina = np.sin(ra_rad)

            x = d_pc * cosd * cosa
            y = d_pc * cosd * sina
            z = d_pc * sind

            mu_ra = pmra / 1000.0
            mu_dec = pmdec / 1000.0

            v_ra = K * mu_ra * d_pc
            v_dec = K * mu_dec * d_pc

            e_ra = np.array([-sina, cosa, 0.0])
            e_dec = np.array([-cosa*sind, -sina*sind, cosd])
            e_r = np.array([x,y,z]) / d_pc

            v = v_ra*e_ra + v_dec*e_dec + rv*e_r
            v *= KM_S_TO_PC_YR

            x2 = x + v[0]*DELTA_T
            y2 = y + v[1]*DELTA_T
            z2 = z + v[2]*DELTA_T

            r = np.sqrt(x2**2 + y2**2 + z2**2)

            dec2 = np.arcsin(z2/r)
            ra2 = np.arctan2(y2,x2)

            ra2 = np.rad2deg(ra2) % 360.0
            dec2 = np.rad2deg(dec2)

        else:

            pmra_deg = (pmra / (3600.0*1000.0)) / np.cos(np.deg2rad(dec))
            pmdec_deg = pmdec / (3600.0*1000.0)

            ra2 = (ra + pmra_deg*DELTA_T) % 360.0
            dec2 = dec + pmdec_deg*DELTA_T

        doc["ra_J2000"] = float(ra2)
        doc["dec_J2000"] = float(dec2)
        doc["CalculatedJ2000"] = True

    except:
        doc["CalculatedJ2000"] = False

    return doc

# ==========================================
# PROCESAMIENTO
# ==========================================

def procesar_archivo(args):

    archivo, global_counter, lock, start_time = args

    client = MongoClient(
        "mongodb://localhost:27017/?w=1&journal=false",
        maxPoolSize=200
    )

    collection = client[DB_NAME].get_collection(
        COLLECTION_NAME,
        write_concern=WriteConcern(w=1, j=False)
    )

    ruta = os.path.join(ORIGEN, archivo)

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

                doc = calcular_j2000(doc)
                batch.append(doc)

            except:
                continue

            if len(batch) >= BATCH_SIZE:

                collection.insert_many(batch, ordered=False)

                with lock:
                    global_counter.value += len(batch)

                    elapsed = time.time() - start_time
                    speed = global_counter.value / elapsed if elapsed > 0 else 0

                    progress = (global_counter.value / TOTAL_REGISTROS) * 100
                    remaining = TOTAL_REGISTROS - global_counter.value
                    eta_seconds = remaining / speed if speed > 0 else 0
                    eta_hours = eta_seconds / 3600

                    finish_timestamp = datetime.now().timestamp() + eta_seconds
                    finish_str = datetime.fromtimestamp(
                        finish_timestamp
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    print(
                        f"[GLOBAL] "
                        f"{global_counter.value:,} / {TOTAL_REGISTROS:,} "
                        f"({progress:.3f}%) | "
                        f"{speed:,.0f} reg/s | "
                        f"ETA: {eta_hours:.2f} h | "
                        f"Fin: {finish_str}"
                    )

                batch = []

        if batch:
            collection.insert_many(batch, ordered=False)
            with lock:
                global_counter.value += len(batch)

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print("\n==========================================")
    print(" GAIA DR3 INGEST + J2000 ENGINE")
    print("==========================================")
    print(f"Total objetivo: {TOTAL_REGISTROS:,} registros")
    print(f"Workers: {MAX_WORKERS}")
    print("==========================================\n")

    client = MongoClient("mongodb://localhost:27017/")
    collection = client[DB_NAME][COLLECTION_NAME]

    print("Eliminando colección previa...")
    collection.drop()
    print("Colección limpia.\n")

    manager = multiprocessing.Manager()
    global_counter = manager.Value('i', 0)
    lock = manager.Lock()

    archivos = sorted([f for f in os.listdir(ORIGEN) if f.endswith(".gz")])

    start_time = time.time()

    args = [(a, global_counter, lock, start_time) for a in archivos]

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(procesar_archivo, args)

    total_time = (time.time()-start_time)/3600

    print("\n==========================================")
    print(f"TOTAL INSERTADO: {global_counter.value:,}")
    print(f"TIEMPO TOTAL: {total_time:.2f} horas")
    print("==========================================")