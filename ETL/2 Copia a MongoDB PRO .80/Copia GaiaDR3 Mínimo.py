# ============================================================
# COPIA MASIVA MONGO LOCAL -> REMOTO (VERSIÓN WAN ROBUSTA)
#
# Qué hace:
# - Lee desde Mongo local
# - Escribe en Mongo remoto
# - Si falla red/escritura: reintenta infinito
# - Nunca avanza al siguiente batch hasta confirmar este
# - No sobrescribe el campo _id
# - Usa source_id como clave funcional de sincronización
# - Pensado para enlaces inestables / VPN / WAN
# ============================================================

from pymongo import MongoClient, UpdateOne
from pymongo.errors import AutoReconnect, BulkWriteError
import time

# ============================================================
# CONFIG
# ============================================================

COLLECTION_NAME = "Gaia DR3"

BATCH_SIZE = 10000
CURSOR_BATCH = 3000
SLEEP_RETRY = 5

MONGO_LOCAL = "mongodb://127.0.0.1:27017/"
MONGO_REMOTO = "mongodb://192.168.200.80:27017/?compressors=zstd"

DB_NAME = "TFM"

# ============================================================
# CLIENTES
# ============================================================

client = MongoClient(
    MONGO_LOCAL,
    socketTimeoutMS=0,
    serverSelectionTimeoutMS=5000,
    retryWrites=False
)

target_client = MongoClient(
    MONGO_REMOTO,
    socketTimeoutMS=0,
    serverSelectionTimeoutMS=5000,
    retryWrites=False
)

db = client[DB_NAME]
target_db = target_client[DB_NAME]

source = db[COLLECTION_NAME]
target = target_db[COLLECTION_NAME]

# ============================================================
# PROYECCIÓN
# ============================================================

projection = {
    "_id": 0,
    "source_id": 1,
    "ra_J2000": 1,
    "dec_J2000": 1,
    "has_xp_sampled": 1,
    "bp_rp": 1,
    "phot_g_mean_mag": 1,
    "teff_gspphot": 1,
    "phot_bp_mean_mag": 1,
    "phot_rp_mean_mag": 1,
    "distance_gspphot": 1,
    "classprob_dsc_combmod_quasar": 1,
    "classprob_dsc_combmod_galaxy": 1,
    "classprob_dsc_combmod_star": 1,
    "parallax": 1,
    "matched_transits": 1
}

# ============================================================
# BULK INFINITO ROBUSTO
# ============================================================

def bulk_write_forever(collection, ops, last_id):
    intento = 0

    while True:
        intento += 1

        try:
            result = collection.bulk_write(ops, ordered=False)
            return result

        except AutoReconnect as e:
            print(f"⚠️ AutoReconnect batch {last_id} intento #{intento}: {e}")

        except BulkWriteError as e:
            print(f"⚠️ BulkWriteError batch {last_id} intento #{intento}: {e.details}")

        except Exception as e:
            print(f"⚠️ Error batch {last_id} intento #{intento}: {e}")

        print(f"⏳ Esperando {SLEEP_RETRY}s antes de reintentar...")
        time.sleep(SLEEP_RETRY)

# ============================================================
# PREPARACIÓN DESTINO
# ============================================================

print("PING LOCAL :", client.admin.command("ping"))
print("PING REMOTO:", target_client.admin.command("ping"))

print("Verificando índice único por source_id en destino...")
target.create_index("source_id", unique=True, background=True)

# ============================================================
# PROCESO
# ============================================================

batch = []
total_read = 0
total_batches = 0
start = time.time()
last_print = start
last_id = None

with client.start_session() as session:

    cursor = source.find(
        {},
        projection,
        no_cursor_timeout=True,
        session=session
    ).hint("source_id_1").sort("source_id", 1).batch_size(CURSOR_BATCH)

    try:
        for doc in cursor:
            total_read += 1
            last_id = doc["source_id"]

            # Muy importante:
            # NO se asigna doc["_id"]
            # Mongo remoto generará _id automáticamente en inserciones nuevas
            # y en existentes hará match por source_id
            batch.append(
                UpdateOne(
                    {"source_id": last_id},
                    {"$set": doc},
                    upsert=True
                )
            )

            if len(batch) >= BATCH_SIZE:
                bulk_write_forever(target, batch, last_id)
                total_batches += 1
                batch = []

                now = time.time()
                if now - last_print >= 2:
                    elapsed = now - start
                    speed = total_read / elapsed if elapsed > 0 else 0

                    print(
                        f"Leídos: {total_read:,} | "
                        f"Batches OK: {total_batches:,} | "
                        f"{speed:,.0f} reg/s | "
                        f"último source_id={last_id}"
                    )

                    last_print = now

    finally:
        cursor.close()

# ============================================================
# ÚLTIMO BATCH
# ============================================================

if batch:
    bulk_write_forever(target, batch, last_id)
    total_batches += 1

# ============================================================
# FINAL
# ============================================================

elapsed = time.time() - start

print("\n===== FINAL =====")
print("Total leídos:", f"{total_read:,}")
print("Batches:", f"{total_batches:,}")
print("Tiempo:", round(elapsed, 1), "s")
print("Último source_id:", last_id)