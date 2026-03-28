from pymongo import MongoClient, InsertOne
import time
from pymongo.write_concern import WriteConcern

client = MongoClient("mongodb://localhost:27017/?compressors=zstd,zlib")
db = client["TFM"]

target_client = MongoClient("mongodb://192.168.200.80:27017/?compressors=zstd,zlib")
target_db = target_client["TFM"]

source = db["Gaia DR3"]
target = target_db.get_collection("Gaia DR3 Reduced",write_concern=WriteConcern(w=0)
)

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

BATCH_SIZE = 100_000

batch = []
total_inserted = 0

start_time = time.time()

# 🔥 SESIÓN EXPLÍCITA
with client.start_session() as session:

    cursor = source.find(
        {},
        projection,
        no_cursor_timeout=True,
        session=session
    )

    try:
        for doc in cursor:
            batch.append(InsertOne(doc))

            if len(batch) >= BATCH_SIZE:
                target.bulk_write(batch, ordered=False)
                total_inserted += len(batch)
                batch = []

                print(f"Insertados: {total_inserted:,}")

    finally:
        cursor.close()

# último batch
if batch:
    target.bulk_write(batch, ordered=False)
    total_inserted += len(batch)

end_time = time.time()

print("\n===== FINAL =====")
print(f"Total insertados: {total_inserted:,}")
print(f"Tiempo total: {end_time - start_time:.1f} s")