from pymongo import MongoClient, InsertOne
from pymongo.write_concern import WriteConcern
import time

client = MongoClient("mongodb://localhost:27017/?compressors=zstd")
target_client = MongoClient("mongodb://192.168.200.80:27017/?compressors=zstd")

db = client["TFM"]
target_db = target_client["TFM"]

source = db["F4:P1 -> Gaia DR3 Galactocentric"]
target = target_db.get_collection(
    "F4:P1 -> Gaia DR3 Galactocentric",
    write_concern=WriteConcern(w=0)
)

BATCH_SIZE = 200_000

total = 0
start = time.time()

with client.start_session() as session:

    cursor = source.find({}, no_cursor_timeout=True, session=session).batch_size(200_000)

    batch = []

    try:
        for doc in cursor:
            doc.pop("_id", None)  # evitar conflictos
            batch.append(InsertOne(doc))
            total += 1

            if len(batch) >= BATCH_SIZE:
                target.bulk_write(batch, ordered=False)
                batch = []

                elapsed = time.time() - start
                rate = total / elapsed

                print(f"{total:,} docs | {rate:,.0f} docs/s")

    finally:
        cursor.close()

if batch:
    target.bulk_write(batch, ordered=False)

print("\nFINAL:", total)