from pymongo import MongoClient

# Conexión al cliente de MongoDB
client = MongoClient('mongodb://localhost:27017')

# Seleccionar la base de datos
db = client['TFM']

# Seleccionar la colección original
original_collection = db['F1:P2 -> MILLIQUAS con Distancia']

# Crear la nueva colección
new_collection = db['F1:P3 -> MILLIQUAS con Distancia Renombrada']

# Iterar sobre los documentos en la colección original
for doc in original_collection.find():
    # Crear un nuevo documento con los campos renombrados
    new_doc = {
        'Millq_RA': doc['RA'],
        'Millq_DEC': doc['DEC'],
        'Millq_NAME': doc['NAME'],
        'Millq_TYPE': doc['TYPE'],
        'Millq_RMAG': doc['RMAG'],
        'Millq_BMAG': doc['BMAG'],
        'Millq_COMMENT': doc['COMMENT'],
        'Millq_R': doc['R'],
        'Millq_B': doc['B'],
        'Millq_Z': doc['Z'],
        'Millq_RXPCT': doc['RXPCT'],
        'Millq_QPCT': doc['QPCT'],
        'Millq_Distancia': doc['Millq_Distancia'],
    }

    # Insertar el nuevo documento en la nueva colección
    new_collection.insert_one(new_doc)
