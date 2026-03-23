from pymongo import MongoClient

# Establecer conexión con MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

# Contador inicial
numRegistro = 0

# Obtener todos los documentos (podrías considerar añadir un filtro si es necesario)
for documento in collection.find():
    # Actualizar el documento actual con el nuevo campo contador
    collection.update_one({'_id': documento['_id']}, {'$set': {'numRegistro': numRegistro}})
    # Incrementar el contador para el siguiente documento
    numRegistro += 1
    if numRegistro % 1000 == 0:  # Informa cada 1000 documentos procesados
        print(f'Procesando registro {numRegistro}')

print("Todos los documentos han sido actualizados con un contador.")