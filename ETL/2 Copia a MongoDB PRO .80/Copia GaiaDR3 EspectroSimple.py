from pymongo import MongoClient, InsertOne
from pymongo.errors import AutoReconnect, BulkWriteError
import time
import os

# =========================
# CONFIG
# =========================

BATCH_SIZE = 40000
CURSOR_BATCH = 2000
MAX_RETRIES = 2
SLEEP_RETRY = 2

COLLECTION_NAME = "F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3"
CHECKPOINT_FILE = "checkpoint_JOIN.txt"

# 🔥 CAMPO CORRECTO
ID_FIELD = "GaiaSpec_Source_id"

# =========================
# CLIENTES
# =========================

client = MongoClient("mongodb://localhost:27017/?compressors=zstd")
target_client = MongoClient("mongodb://192.168.200.80:27017/?compressors=zstd")

db = client["TFM"]
target_db = target_client["TFM"]

source = db[COLLECTION_NAME]
target = target_db[COLLECTION_NAME]

# =========================
# CHECKPOINT
# =========================

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return int(f.read().strip())
    return None

def save_checkpoint(value):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(value))

last_id = load_checkpoint()

query = {}
if last_id:
    query = {ID_FIELD: {"$gt": last_id}}
    print(f"🔁 Reanudando desde {ID_FIELD} > {last_id}")

# =========================
# BULK WRITE
# =========================

def bulk_write_retry(collection, batch):
    for attempt in range(MAX_RETRIES):
        try:
            collection.bulk_write(batch, ordered=False)
            return True

        except BulkWriteError as bwe:
            if all(e["code"] == 11000 for e in bwe.details.get("writeErrors", [])):
                return True
            else:
                print("❌ Error en bulk:", bwe.details)
                return False

        except AutoReconnect as e:
            print(f"⚠️ Retry {attempt+1}: {e}")
            time.sleep(SLEEP_RETRY)

    return False

# =========================
# PROCESO
# =========================

def run_etl():
    batch = []
    total_inserted = 0

    start_time = time.time()
    last_print = start_time

    cursor = source.find(
        query,
        no_cursor_timeout=True
    ).sort(ID_FIELD, 1).batch_size(CURSOR_BATCH)

    try:
        for doc in cursor:

            doc.pop("_id", None)  # 🔥 nuevo _id en destino

            batch.append(InsertOne(doc))

            last_processed_id = doc.get(ID_FIELD)

            if len(batch) >= BATCH_SIZE:

                ok = bulk_write_retry(target, batch)

                if ok:
                    total_inserted += len(batch)
                    if last_processed_id:
                        save_checkpoint(last_processed_id)

                batch = []

                now = time.time()
                if now - last_print > 2:
                    elapsed = now - start_time
                    speed = total_inserted / elapsed if elapsed > 0 else 0

                    print(
                        f"Insertados: {total_inserted:,} | "
                        f"{speed:,.0f} reg/s | "
                        f"{int(elapsed)}s"
                    )

                    last_print = now

    finally:
        cursor.close()

    if batch:
        if bulk_write_retry(target, batch):
            total_inserted += len(batch)
            if last_processed_id:
                save_checkpoint(last_processed_id)

    elapsed = time.time() - start_time

    print("\n===== FINAL =====")
    print(f"Total insertados: {total_inserted:,}")
    print(f"Tiempo total: {elapsed:.1f} s")
    print(f"Velocidad media: {total_inserted/elapsed:,.0f} reg/s")

# =========================

if __name__ == "__main__":
    print("🚀 ETL JOIN Gaia Spectrum")
    run_etl()