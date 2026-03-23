from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

# Actualiza todos los documentos
resultado = collection.update_many(
    {}, # Filtro vacío, lo que significa que la actualización se aplica a todos los documentos
    {'$set': {'CalculatedJ2000': False}} # Añade el campo CalculatedJ2000 con el valor False
)

# Imprime el número de documentos actualizados
print(f"Documentos actualizados: {resultado.modified_count}")