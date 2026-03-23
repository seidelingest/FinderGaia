# ==========================================
# IMPORTS
# ==========================================

import numpy as np
import matplotlib.pyplot as plt
from pymongo import MongoClient
from matplotlib.colors import LogNorm

# ==========================================
# CONEXIÓN MONGODB
# ==========================================

client = MongoClient("mongodb://localhost:27017/")
db = client["TFM"]

collection = db["F5:P1 -> HR Enriquecido"]

# ==========================================
# PARÁMETROS
# ==========================================

BINS = 1000
XRANGE = [-1, 5]
YRANGE = [-5, 15]

CHUNK_SIZE = 1_000_000

# histograma acumulado
H = np.zeros((BINS, BINS))

xedges = np.linspace(XRANGE[0], XRANGE[1], BINS + 1)
yedges = np.linspace(YRANGE[0], YRANGE[1], BINS + 1)

# ==========================================
# CONSULTA
# ==========================================

cursor = collection.find(
    {
        "absolute_mag_g": {"$ne": None},
        "color_bp_rp": {"$ne": None}
    },
    {
        "_id": 0,
        "absolute_mag_g": 1,
        "color_bp_rp": 1
    },
    batch_size=CHUNK_SIZE
)

# ==========================================
# PROCESAMIENTO STREAMING
# ==========================================

print("Procesando estrellas...")

bp_chunk = []
mg_chunk = []

count = 0

for doc in cursor:

    bp_chunk.append(doc["color_bp_rp"])
    mg_chunk.append(doc["absolute_mag_g"])

    count += 1

    if len(bp_chunk) == CHUNK_SIZE:

        bp_array = np.array(bp_chunk)
        mg_array = np.array(mg_chunk)

        H_chunk, _, _ = np.histogram2d(
            bp_array,
            mg_array,
            bins=[xedges, yedges]
        )

        H += H_chunk

        bp_chunk.clear()
        mg_chunk.clear()

        print(f"Procesadas: {count:,}")

# último bloque
if bp_chunk:

    bp_array = np.array(bp_chunk)
    mg_array = np.array(mg_chunk)

    H_chunk, _, _ = np.histogram2d(
        bp_array,
        mg_array,
        bins=[xedges, yedges]
    )

    H += H_chunk

print("Total estrellas:", count)

# ==========================================
# GRÁFICO
# ==========================================

plt.figure(figsize=(8,10))

plt.imshow(
    H.T,
    origin="lower",
    aspect="auto",
    extent=[XRANGE[0], XRANGE[1], YRANGE[0], YRANGE[1]],
    cmap="inferno",
    norm=LogNorm()
)

plt.gca().invert_yaxis()

plt.xlabel("BP − RP (color)")
plt.ylabel("Absolute magnitude $M_G$")
plt.title("Gaia DR3 Hertzsprung–Russell Diagram")

cbar = plt.colorbar()
cbar.set_label("Star density (log scale)")

plt.text(1.5, 8, "Main Sequence", color="white", fontsize=14)
plt.text(3.5, 0, "Red Giants", color="white", fontsize=14)
plt.text(1.1, -0.5, "Red Clump", color="white", fontsize=13)
plt.text(0.2, 12.5, "White Dwarfs", color="white", fontsize=13)
plt.text(1.0, 3.0, "Subgiants", color="white", fontsize=13)

plt.show()