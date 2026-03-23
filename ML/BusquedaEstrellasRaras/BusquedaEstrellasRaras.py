import numpy as np
import time
from pymongo import MongoClient
from sklearn.neighbors import KernelDensity

# =========================================================
# INICIO DEL PROGRAMA
# =========================================================

print("==============================================")
print("   BÚSQUEDA DE ESTRELLAS EXÓTICAS EN GAIA DR3 ")
print("   Método: Rareza por densidad en diagrama HR ")
print("==============================================\n")

start_time = time.time()

# =========================================================
# CONEXIÓN A MONGODB
# =========================================================

print("Conectando a MongoDB...")

client = MongoClient("mongodb://localhost:27017/")
db = client["TFM"]

collection = db["F5:P1 -> HR Enriquecido"]

print("Conexión establecida.\n")

# =========================================================
# CONSULTA A LA BASE DE DATOS
# =========================================================

print("Preparando consulta de estrellas con datos HR válidos...")

cursor = collection.find(
    {
        "absolute_mag_g": {"$ne": None},
        "color_bp_rp": {"$ne": None}
    },
    {
        "_id": 0,
        "source_id": 1,
        "absolute_mag_g": 1,
        "color_bp_rp": 1
    }
)

# =========================================================
# LECTURA DE DATOS
# =========================================================

print("Leyendo estrellas desde MongoDB...\n")

bp = []     # Color BP-RP
mg = []     # Magnitud absoluta
ids = []    # Identificador Gaia

count = 0

for doc in cursor:

    ids.append(doc["source_id"])
    bp.append(doc["color_bp_rp"])
    mg.append(doc["absolute_mag_g"])

    count += 1

    # Mostrar progreso cada millón de estrellas
    if count % 1_000_000 == 0:
        print(f"Estrellas leídas: {count:,}")

print(f"\nLectura finalizada.")
print(f"Total estrellas cargadas: {count:,}\n")

# =========================================================
# CONVERSIÓN A ARRAYS NUMPY
# =========================================================

print("Convirtiendo datos a arrays NumPy...")

bp = np.array(bp)
mg = np.array(mg)
ids = np.array(ids)

# Construimos matriz de características
# Cada fila representa una estrella:
# [color, magnitud]
X = np.vstack([bp, mg]).T

print("Dimensión del dataset:", X.shape, "\n")

# =========================================================
# CÁLCULO DE DENSIDAD DEL HR DIAGRAM
# =========================================================

print("Estimando densidad estelar en el diagrama HR...")
print("Este paso puede tardar dependiendo del número de estrellas.\n")

kde = KernelDensity(kernel='gaussian', bandwidth=0.1)

kde_start = time.time()

# Ajustar el modelo de densidad
kde.fit(X)

print("Modelo KDE ajustado.")

# Evaluar densidad en cada estrella
density = np.exp(kde.score_samples(X))

print("Densidad calculada para todas las estrellas.\n")

# =========================================================
# CÁLCULO DE RAREZA
# =========================================================

print("Calculando índice de rareza...")

# Rareza inversamente proporcional a densidad
rare_score = 1 / density

print("Rareza calculada.\n")

# =========================================================
# SELECCIÓN DE OBJETOS MÁS RAROS
# =========================================================

print("Buscando las estrellas más raras del catálogo...")

# Ordenar por rareza
idx = np.argsort(rare_score)[-1000:]

rare_stars = []

for i in idx:
    rare_stars.append({
        "source_id": int(ids[i]),
        "bp_rp": float(bp[i]),
        "absolute_mag_g": float(mg[i]),
        "rarity_score": float(rare_score[i])
    })

print("\nSelección completada.")
print("Se han identificado 1000 candidatos raros.\n")

# =========================================================
# MOSTRAR RESULTADOS
# =========================================================

print("==============================================")
print("   TOP ESTRELLAS MÁS RARAS DEL CATÁLOGO")
print("==============================================\n")

for star in rare_stars[:20]:
    print(star)

# =========================================================
# ESTADÍSTICAS FINALES
# =========================================================

elapsed = time.time() - start_time

print("\n==============================================")
print("Proceso finalizado.")
print(f"Tiempo total: {elapsed:.2f} segundos")
print("==============================================")