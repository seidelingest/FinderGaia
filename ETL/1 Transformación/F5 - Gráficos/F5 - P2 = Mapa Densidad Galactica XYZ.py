# ==========================================================
# GAIA DR3 GALACTIC DISK DENSITY MAP
# ==========================================================

import time
import numpy as np
import matplotlib.pyplot as plt
from pymongo import MongoClient

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"
COLLECTION = "F5:P2 -> Gaia DR3 XYZ"

FIELD_X = "X"
FIELD_Y = "Y"

XY_MIN = -20
XY_MAX = 20

BINS = 800

BLOCK_SIZE = 300000
MONGO_BATCH_SIZE = 300000

OUTPUT_FILE = "galactic_disk_density_gaia.png"

PRINT_STEP = 5_000_000

# ==========================================================
# INICIO
# ==========================================================

print("===================================================")
print("GAIA DR3 GALACTIC DISK DENSITY MAP")
print("===================================================")

t_inicio = time.time()

print("Conectando a MongoDB...")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION]

print("Conexión establecida.")

# ==========================================================
# DIAGNÓSTICO
# ==========================================================

doc = collection.find_one({}, {"_id":0})
print("Documento de prueba:", doc)

# ==========================================================
# CONTAR DOCUMENTOS
# ==========================================================

print("\nContando documentos...")

total_docs = collection.estimated_document_count()

print(f"Total documentos en la colección: {total_docs:,}")

# ==========================================================
# HISTOGRAMA GLOBAL
# ==========================================================

density = np.zeros((BINS, BINS), dtype=np.float64)

x_block = []
y_block = []

leidos = 0
validos = 0

# ==========================================================
# LECTURA STREAMING
# ==========================================================

print("\nIniciando lectura del catálogo...")

with client.start_session() as session:

    cursor = collection.find(
        {},
        {FIELD_X:1, FIELD_Y:1, "_id":0},
        batch_size=MONGO_BATCH_SIZE,
        no_cursor_timeout=True,
        session=session
    )

    try:

        for doc in cursor:

            leidos += 1

            x = doc.get(FIELD_X)
            y = doc.get(FIELD_Y)

            if x is None or y is None:
                continue

            x_block.append(x)
            y_block.append(y)

            validos += 1

            if len(x_block) >= BLOCK_SIZE:

                H, _, _ = np.histogram2d(
                    x_block,
                    y_block,
                    bins=BINS,
                    range=[[XY_MIN,XY_MAX],[XY_MIN,XY_MAX]]
                )

                density += H

                x_block.clear()
                y_block.clear()

            # progreso
            if leidos % PRINT_STEP == 0:

                dt = time.time() - t_inicio
                velocidad = leidos / dt

                progreso = (leidos / total_docs) * 100

                restante = total_docs - leidos
                eta = restante / velocidad if velocidad > 0 else 0

                horas = eta / 3600

                print(
                    f"Leídas: {leidos:,} | "
                    f"Progreso: {progreso:.2f}% | "
                    f"Velocidad: {velocidad:,.0f} estrellas/s | "
                    f"ETA: {horas:.2f} h"
                )

    finally:
        cursor.close()

# ==========================================================
# PROCESAR BLOQUE FINAL
# ==========================================================

if len(x_block) > 0:

    H, _, _ = np.histogram2d(
        x_block,
        y_block,
        bins=BINS,
        range=[[XY_MIN,XY_MAX],[XY_MIN,XY_MAX]]
    )

    density += H

print("\nLectura finalizada.")
print(f"Total leídas: {leidos:,}")
print(f"Total válidas: {validos:,}")

# ==========================================================
# DIAGNÓSTICO HISTOGRAMA
# ==========================================================

suma_total = density.sum()
max_celda = density.max()

print("\nDiagnóstico del histograma:")
print(f"Total estrellas contabilizadas: {int(suma_total):,}")
print(f"Máxima densidad en una celda: {int(max_celda):,}")

if suma_total == 0:
    raise ValueError("El histograma está vacío.")

# ==========================================================
# ESCALA LOG
# ==========================================================

density_log = np.log10(density + 1)

# ==========================================================
# GRÁFICO
# ==========================================================

print("\nGenerando gráfico...")

plt.figure(figsize=(10,10))

img = plt.imshow(
    density_log.T,
    origin="lower",
    extent=[XY_MIN,XY_MAX,XY_MIN,XY_MAX],
    cmap="inferno",
    interpolation="bicubic"
)

plt.colorbar(img,label="log10(stars)")

plt.xlabel("X (kpc)")
plt.ylabel("Y (kpc)")
plt.title("Gaia DR3 Galactic Disk Density")

# posición aproximada del Sol
plt.scatter(-8.2,0,color="cyan",s=80,label="Sun")

plt.legend()

plt.tight_layout()

plt.savefig(OUTPUT_FILE,dpi=300)

plt.show()

# ==========================================================
# FIN
# ==========================================================

t_fin = time.time()

print("\n===================================================")
print("Proceso completado")
print(f"Tiempo total: {(t_fin - t_inicio)/3600:.2f} horas")
print(f"Imagen guardada en: {OUTPUT_FILE}")
print("===================================================")