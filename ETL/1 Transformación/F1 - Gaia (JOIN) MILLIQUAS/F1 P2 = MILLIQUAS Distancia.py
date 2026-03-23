from pymongo import MongoClient
import numpy as np

# Conectar al servidor de MongoDB (reemplaza '<mongodb_uri>' con tu URI de MongoDB)
client = MongoClient('mongodb://localhost:27017/')

# Acceder a la base de datos (reemplaza '<db_name>' con el nombre de tu base de datos)
db = client['TFM']

# Acceder a las colecciones
coll_milliquas = db['MILLIQUAS']
coll_copy = db['F1:P2 -> MILLIQUAS con Distancia']

# Borrar datos colección destino
print('Borrando datos de la colección')
coll_copy.delete_many({})

i = 0

# Iterar sobre cada documento en la colección original
for doc in coll_milliquas.find():
    i = i + 1

    # Copiar el documento
    doc_copy = doc.copy()

    # Calcula la distancia_J2000 (reemplaza 'ra' y 'dec' con los nombres correctos de los campos)
    ra = doc['RA']
    dec = doc['DEC']
    vector = np.array([ra, dec])
    distancia_j2000 = np.linalg.norm(vector)

    # Añadir la distancia_J2000 al documento copiado
    doc_copy['Millq_Distancia'] = round(distancia_j2000 * 10000000, 0)

    # Insertar el documento copiado en la nueva colección
    coll_copy.insert_one(doc_copy)

    if i % 1000 == 0:
        print(i);