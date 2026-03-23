from astropy.coordinates import SkyCoord, FK5
from astropy.time import Time
from astropy import units as u
from pymongo import MongoClient
import numpy as np

# Configura tu cliente MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['F1:P1 -> Gaia DR3 + Gaia QsoC']

i = 0

# Itera sobre cada documento en la colección
for doc in collection.find():
    i = i + 1

    # Obtiene las coordenadas actuales en J2016
    ra_J2016 = doc['Gaia_ra_J2016']
    dec_J2016 = doc['Gaia_dec_J2016']

    # Convierte las coordenadas a SkyCoord en el marco de referencia actual
    coord_J2016 = SkyCoord(ra_J2016, dec_J2016, frame='icrs', unit='deg', obstime=Time('J2016'))

    # Precess the coordinates to J2000
    coord_J2000 = coord_J2016.transform_to(FK5(equinox=Time('J2000')))

    # Redondeo
    coord_J2000.ra.deg = round(coord_J2000.ra.deg, 7)
    coord_J2000.dec.deg = round(coord_J2000.dec.deg, 7)

    # Calcular el valor "Distancia" como idea sintética
    vector = np.array([coord_J2000.ra.deg, coord_J2000.dec.deg])
    distancia_j2000 = round ( np.linalg.norm(vector) * 10000000, 0 )

    # Actualiza el documento con las nuevas coordenadas
    collection.update_one(
        {'_id': doc['_id']},
        {'$set':
            {
                'Gaia_ra_J2000': coord_J2000.ra.deg,
                'Gaia_dec_J2000': coord_J2000.dec.deg,
                'Gaia_Distancia': distancia_j2000
            }
        }
    )

    if i % 1000 == 0:
        print(i);
