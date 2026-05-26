import os
import gzip
import pandas as pd
from pymongo import MongoClient, InsertOne
from concurrent.futures import ThreadPoolExecutor

# =========================
# CONFIG
# =========================

BATCH_SIZE = 5000
CHUNK_SIZE = 2000
MAX_WORKERS = 4  # Ajustar según CPU / disco

DIRECTORIO = r'O:\Catalogo Gaia\DR3\xp_sampled_mean_spectrum'

# =========================
# MONGO
# =========================

client = MongoClient(
    'mongodb://localhost:27017/?compressors=zstd',
    maxPoolSize=10,
    retryWrites=False
)

db = client['TFM']
collection = db['Gaia DR3 XP Sampled Mean Spectrum']

print('🧹 Borrando colección...')
collection.delete_many({})

# (Opcional) índice para consultas
collection.create_index("source_id")

# =========================
# FUNCIONES
# =========================

def string_to_float_list_fast(s):
    # Conversión rápida sin overhead innecesario
    return list(map(float, s.strip("[]").split(",")))


def procesar_archivo(archivo):

    ruta = os.path.join(DIRECTORIO, archivo)
    print(f"🚀 Procesando {archivo}")

    operaciones = []
    total = 0

    with gzip.open(ruta, 'rt') as f:

        # Leer CSV correctamente (sin next manual)
        reader = pd.read_csv(
            f,
            skiprows=63,
            chunksize=CHUNK_SIZE
        )

        for chunk in reader:

            # Conversión columnas pesadas
            chunk["flux"] = chunk["flux"].map(string_to_float_list_fast)
            chunk["flux_error"] = chunk["flux_error"].map(string_to_float_list_fast)

            # Preparar documentos
            for doc in chunk.to_dict('records'):

                # 🔥 CLAVE: eliminar _id SIEMPRE
                doc.pop('_id', None)

                operaciones.append(InsertOne(doc))

            # Insert batch
            if len(operaciones) >= BATCH_SIZE:
                collection.bulk_write(operaciones, ordered=False)
                total += len(operaciones)
                print(f"{archivo} -> {total} docs")
                operaciones = []

    # Último batch
    if operaciones:
        collection.bulk_write(operaciones, ordered=False)
        total += len(operaciones)

    print(f"✅ {archivo} completado -> {total} docs")


# =========================
# EJECUCIÓN
# =========================

archivos = [f for f in os.listdir(DIRECTORIO) if f.endswith('.gz')]

print(f"📦 Total archivos: {len(archivos)}")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    executor.map(procesar_archivo, archivos)

print("🎯 ETL FINALIZADO")