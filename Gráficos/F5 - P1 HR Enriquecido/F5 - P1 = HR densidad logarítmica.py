# ==========================================================
# HR DIAGRAM CON DENSIDAD LOGARÍTMICA
# OPTIMIZADO PARA LECTURA DESDE HDD SAS
# ==========================================================

import time
import math
import numpy as np
import matplotlib.pyplot as plt
from pymongo import MongoClient


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"
COLLECTION = "F5:P1 -> HR Enriquecido"

FIELD_COLOR = "color_bp_rp"
FIELD_MAG = "absolute_mag_g"

# rango HR
COLOR_MIN = -1.0
COLOR_MAX = 5.0
MAG_MIN = -5.0
MAG_MAX = 18.0

# resolución del histograma
BINS_X = 1200
BINS_Y = 1200

# tamaño de lote de lectura desde MongoDB
BATCH_SIZE = 200000

OUTPUT_FILE = "HR_densidad_log.png"


# ==========================================================
# VALIDACIÓN DE VALORES
# ==========================================================

def valor_valido(x):

    if x is None:
        return False

    if not isinstance(x, (int, float)):
        return False

    if math.isnan(x) or math.isinf(x):
        return False

    return True


# ==========================================================
# INICIO
# ==========================================================

print("============================================")
print(" HR DIAGRAM - DENSIDAD LOGARÍTMICA")
print("============================================")

t0 = time.time()

print("Conectando a MongoDB...")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION]

print("Conectado.")


# ==========================================================
# QUERY OPTIMIZADA
# ==========================================================

query = {
    FIELD_COLOR: {"$gte": COLOR_MIN, "$lte": COLOR_MAX},
    FIELD_MAG: {"$gte": MAG_MIN, "$lte": MAG_MAX}
}

projection = {
    "_id": 0,
    FIELD_COLOR: 1,
    FIELD_MAG: 1
}


# ==========================================================
# LECTURA DESDE MONGODB
# ==========================================================

colors = []
magnitudes = []

leidos = 0
validos = 0

print("Iniciando lectura del catálogo...")

with client.start_session() as session:

    cursor = collection.find(
        query,
        projection,
        batch_size=BATCH_SIZE,
        no_cursor_timeout=True,
        session=session
    )

    for doc in cursor:

        leidos += 1

        color = doc.get(FIELD_COLOR)
        mag = doc.get(FIELD_MAG)

        if not valor_valido(color) or not valor_valido(mag):
            continue

        colors.append(color)
        magnitudes.append(mag)

        validos += 1

        if leidos % 1_000_000 == 0:
            print(
                f"Leídos: {leidos:,}   "
                f"Válidos: {validos:,}"
            )

    cursor.close()


print("Lectura finalizada")
print("Total estrellas válidas:", f"{validos:,}")


# ==========================================================
# CONVERSIÓN A NUMPY
# ==========================================================

print("Convirtiendo a arrays NumPy...")

colors = np.array(colors, dtype=np.float32)
magnitudes = np.array(magnitudes, dtype=np.float32)

print("Arrays creados")
print("Tamaño:", colors.shape)


# ==========================================================
# HISTOGRAMA HR
# ==========================================================

print("Calculando histograma HR...")

t_hist = time.time()

H, xedges, yedges = np.histogram2d(

    colors,
    magnitudes,

    bins=[BINS_X, BINS_Y],

    range=[
        [COLOR_MIN, COLOR_MAX],
        [MAG_MIN, MAG_MAX]
    ]
)

print("Histograma calculado en", round(time.time() - t_hist, 2), "s")

print("Máxima densidad celda:", int(H.max()))


# ==========================================================
# ESCALA LOG
# ==========================================================

print("Aplicando escala log...")

H_log = np.log10(H + 1)

H_plot = H_log.T


# ==========================================================
# VISUALIZACIÓN
# ==========================================================

print("Generando gráfico HR...")

plt.figure(figsize=(12, 10))

extent = [COLOR_MIN, COLOR_MAX, MAG_MIN, MAG_MAX]

img = plt.imshow(
    H_plot,
    origin="lower",
    extent=extent,
    aspect="auto",
    interpolation="nearest"
)

plt.colorbar(img, label="log10(N + 1)")

plt.xlabel("BP - RP")
plt.ylabel("Magnitud absoluta G")

plt.title("Diagrama HR con densidad logarítmica")

plt.gca().invert_yaxis()

plt.tight_layout()

plt.savefig(OUTPUT_FILE, dpi=300)

plt.show()


# ==========================================================
# FIN
# ==========================================================

print("============================================")
print("Tiempo total:", round(time.time() - t0, 2), "s")
print("============================================")