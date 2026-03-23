import math
import time
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from concurrent.futures import ThreadPoolExecutor

def convert_coordinates_with_linear_pm(ra_deg, dec_deg, pm_ra_mas, pm_dec_mas, years_diff=-16):
    # Convertir el movimiento propio de RA y Dec de mas/año a grados/año
    # Ajustar pm_ra_deg por el coseno de la declinación
    pm_ra_deg = (pm_ra_mas / (3600 * 1000)) / math.cos(math.radians(dec_deg))
    pm_dec_deg = pm_dec_mas / (3600 * 1000)

    # Calcular nuevas coordenadas ajustando el movimiento propio por el número de años
    ra_2000 = ra_deg + (pm_ra_deg * years_diff)
    dec_2000 = dec_deg + (pm_dec_deg * years_diff)

    return ra_2000, dec_2000

def process_star(star):
    ra_J2016 = star.get('ra')
    dec_J2016 = star.get('dec')
    pmra = star.get('pmra')
    pmdec = star.get('pmdec')

    if None not in (ra_J2016, dec_J2016, pmra, pmdec):
        ra_J2000, dec_J2000 = convert_coordinates_with_linear_pm(ra_J2016, dec_J2016, pmra, pmdec)
        try:
            collection.update_one({'_id': star['_id']},
                                  {'$set': {'ra_J2000': ra_J2000, 'dec_J2000': dec_J2000, 'CalculatedJ2000': True}})
        except BulkWriteError as bwe:
            print(bwe.details)  # Maneja errores de escritura

# Conexión a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

# Contador e inicio del tiempo de ejecución
count = 0
start_time = time.time()

# Configuración del ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=3) as executor:
    stars_to_process = collection.find({"CalculatedJ2000": {"$ne": True}})
    results = executor.map(process_star, stars_to_process)

    # Procesa los resultados (aquí solo incrementamos el contador)
    for result in results:
        count += 1
        elapsed_time = time.time() - start_time
        print(f"Procesando registro {count}. Velocidad: {count / elapsed_time} registros por segundo")
        if count % 10000 == 0:
            elapsed_time = time.time() - start_time
            print(f"Procesando registro {count}. Velocidad: {count / elapsed_time} registros por segundo")

# Informe de finalización
print(f"Proceso completado. {count} registros procesados en {time.time() - start_time} segundos.")
