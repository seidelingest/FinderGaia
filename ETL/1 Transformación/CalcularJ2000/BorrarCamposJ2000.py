from pymongo import MongoClient

# Conexión a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

# Borrar los campos 'dec_J2000' y 'ra_J2000' de todos los documentos
collection.update_many({}, {'$unset': {'dec_J2000': "", 'ra_J2000': ""}})

print("Campos eliminados.")