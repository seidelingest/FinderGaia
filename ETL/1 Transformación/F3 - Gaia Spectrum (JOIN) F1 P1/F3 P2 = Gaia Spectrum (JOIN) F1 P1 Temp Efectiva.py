from pymongo import MongoClient

# Conectar a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']

# Conectar a las colecciones
gaia_spectrum_collection = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3']
gaia_dr3_collection = db['Gaia DR3']

# Inicializar el contador
count = 0
batch_size = 10_000  # Tamaño del lote para el mensaje de progreso

# Iterar sobre cada documento en la colección F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3
for doc in gaia_spectrum_collection.find():
    source_id = doc.get('GaiaSpec_Source_id')
    if source_id:
        # Buscar el documento correspondiente en Gaia DR3 usando Source_id
        gaia_dr3_doc = gaia_dr3_collection.find_one({'source_id': source_id})
        if gaia_dr3_doc:
            # Obtener el campo teff_gspphot
            teff_gspphot = gaia_dr3_doc.get('teff_gspphot')
            if teff_gspphot is not None:
                # Añadir el campo teff_gspphot al documento en F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3
                gaia_spectrum_collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'Gaia_teff_gspphot': teff_gspphot}}
                )
                # print(f"Updated document with Source_id {source_id} to add teff_gspphot: {teff_gspphot}")
            else:
                print(f"No teff_gspphot found for Source_id {source_id}")
        else:
            print(f"No matching document found in Gaia DR3 for Source_id {source_id}")
    else:
        print("No Source_id found in document")

    # Incrementar el contador
    count += 1

    # Mostrar el progreso cada millón de registros
    if count % batch_size == 0:
        print(f"Processed {count} documents...")

print("Update process completed.")
