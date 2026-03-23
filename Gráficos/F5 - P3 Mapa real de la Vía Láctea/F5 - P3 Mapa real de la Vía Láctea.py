import numpy as np
import matplotlib.pyplot as plt
from pymongo import MongoClient

# ==========================================================
# CONFIG
# ==========================================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "TFM"
COLLECTION = "F5:P3 -> Mapa Real Via Lactea"

BINS = 1200   # resolución
LIMIT_KPC = 15  # tamaño del mapa

# ==========================================================
# CONEXIÓN
# ==========================================================

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLLECTION]

# ==========================================================
# HISTOGRAMA VACÍO
# ==========================================================

hist = np.zeros((BINS, BINS), dtype=np.float32)

# ==========================================================
# LECTURA EN STREAMING
# ==========================================================

print("Leyendo datos y acumulando densidad...")

cursor = col.find(
    {},
    {"_id": 0, "X": 1, "Y": 1},
    batch_size=200_000
)

block_size = 200_000
X_block = []
Y_block = []

count = 0

for doc in cursor:
    X_block.append(doc["X"])
    Y_block.append(doc["Y"])
    count += 1

    if len(X_block) >= block_size:

        X = np.array(X_block)
        Y = np.array(Y_block)

        h, _, _ = np.histogram2d(
            X, Y,
            bins=BINS,
            range=[[-LIMIT_KPC, LIMIT_KPC], [-LIMIT_KPC, LIMIT_KPC]]
        )

        hist += h

        X_block.clear()
        Y_block.clear()

    if count % 5_000_000 == 0:
        print(f"Procesadas: {count:,}")

# último bloque
if X_block:
    X = np.array(X_block)
    Y = np.array(Y_block)

    h, _, _ = np.histogram2d(
        X, Y,
        bins=BINS,
        range=[[-LIMIT_KPC, LIMIT_KPC], [-LIMIT_KPC, LIMIT_KPC]]
    )

    hist += h

cursor.close()

print(f"Total procesadas: {count:,}")

# ==========================================================
# ESCALA LOGARÍTMICA
# ==========================================================

hist = np.log10(hist + 1)

# ==========================================================
# PLOT
# ==========================================================

plt.figure(figsize=(10, 10))

plt.imshow(
    hist.T,
    origin="lower",
    extent=[-LIMIT_KPC, LIMIT_KPC, -LIMIT_KPC, LIMIT_KPC]
)

plt.colorbar(label="log10(densidad)")

plt.title("Mapa de la Vía Láctea (Gaia DR3 - estrellas jóvenes)")
plt.xlabel("X [kpc]")
plt.ylabel("Y [kpc]")

plt.tight_layout()
plt.savefig("mapa_via_lactea.png", dpi=300)
plt.show()