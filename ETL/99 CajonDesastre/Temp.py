from pymongo import MongoClient

# Conectar a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']

# Conectar a la colección
gaia_spectrum_collection = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3']

# Eliminar el campo teff_gspphot de todos los documentos
result = gaia_spectrum_collection.update_many({}, {'$unset': {'GaiaSpec_teff_gspphot': ""}})

# Mostrar resultados
print(f"Matched {result.matched_count} documents and modified {result.modified_count} documents to remove the 'teff_gspphot' field.")
