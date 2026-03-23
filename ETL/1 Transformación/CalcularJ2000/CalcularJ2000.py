from pymongo import MongoClient
from astropy.coordinates import SkyCoord, FK5
from astropy.time import Time
import astropy.units as u
from pymongo.errors import BulkWriteError
import time
import math

# Definición de la función convert_coordinates_with_proper_motion aquí

def convert_coordinates_with_proper_motionV2(ra_deg, dec_deg, pm_ra_cosdec, pm_dec, parallax, reference_epoch='J2016'):
    if parallax > 0:
        distance = (1000 / parallax) * u.pc
        coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, distance=distance,
                         pm_ra_cosdec=pm_ra_cosdec * u.mas / u.yr, pm_dec=pm_dec * u.mas / u.yr,
                         frame='icrs', obstime=Time(reference_epoch))
    else:
        coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg,
                         pm_ra_cosdec=pm_ra_cosdec * u.mas / u.yr, pm_dec=pm_dec * u.mas / u.yr,
                         frame='icrs', obstime=Time(reference_epoch))
    coord_transformed = coord.transform_to(FK5(equinox='J2000'))
    return coord_transformed.ra.deg, coord_transformed.dec.deg


# Definición de la función que convierte las coordenadas con un enfoque lineal basado en el movimiento propio
def convert_coordinates_with_linear_pmOLD(ra_deg, dec_deg, pm_ra_mas, pm_dec_mas, years_diff=16):
    # Convertir el movimiento propio de RA y Dec de mas/año a grados/año
    pm_ra_deg = pm_ra_mas / (3600 * 1000)  # milisegundos de arco a grados
    pm_dec_deg = pm_dec_mas / (3600 * 1000)

    # Calcular nuevas coordenadas ajustando el movimiento propio por el número de años
    ra_2000 = ra_deg - (pm_ra_deg * years_diff)
    dec_2000 = dec_deg - (pm_dec_deg * years_diff)

    return ra_2000, dec_2000


def convert_coordinates_with_linear_pm(ra_deg, dec_deg, pm_ra_mas, pm_dec_mas, years_diff=-16):
    # Convertir el movimiento propio de RA y Dec de mas/año a grados/año
    # Ajustar pm_ra_deg por el coseno de la declinación
    pm_ra_deg = (pm_ra_mas / (3600 * 1000)) / math.cos(math.radians(dec_deg))
    pm_dec_deg = pm_dec_mas / (3600 * 1000)

    # Calcular nuevas coordenadas ajustando el movimiento propio por el número de años
    ra_2000 = ra_deg + (pm_ra_deg * years_diff)  # Asumiendo que el movimiento propio es una adición en este caso
    dec_2000 = dec_deg + (pm_dec_deg * years_diff)

    return ra_2000, dec_2000

# Conexión a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

# Contador e inicio del tiempo de ejecución
count = 0
start_time = time.time()

for star in collection.find({"CalculatedJ2000": {"$ne": True}}):
    ra_J2016 = star.get('ra')
    dec_J2016 = star.get('dec')
    pmra = star.get('pmra')
    pmdec = star.get('pmdec')

    if None not in (ra_J2016, dec_J2016, pmra, pmdec):
        # Calcula las nuevas coordenadas para J2000 usando la función lineal
        ra_J2000, dec_J2000 = convert_coordinates_with_linear_pm(
            ra_J2016, dec_J2016, pmra, pmdec
        )

        # Actualiza el documento actual para añadir los nuevos campos calculados
        try:
            collection.update_one({'_id': star['_id']},
                                  {'$set': {'ra_J2000': ra_J2000, 'dec_J2000': dec_J2000, 'CalculatedJ2000': True}})
        except BulkWriteError as bwe:
            print(bwe.details)  # Maneja errores de escritura

    count += 1
    if count % 10000 == 0:
        elapsed_time = time.time() - start_time
        print(f"Procesando registro {count}. Velocidad: {count / elapsed_time} registros por segundo")

# Informe de finalización
print(f"Proceso completado. {count} registros procesados en {time.time() - start_time} segundos.")