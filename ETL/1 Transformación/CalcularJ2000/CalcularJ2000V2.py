import threading
import time
from pymongo import MongoClient
from astropy.coordinates import SkyCoord, FK5
from astropy.time import Time
import astropy.units as u
from pymongo.errors import PyMongoError

client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3']

def convert_coordinates_with_proper_motion(ra_deg, dec_deg, pm_ra_cosdec, pm_dec, parallax, reference_epoch='J2016'):
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

def process_subset(filter_criteria):
    start_time = time.time()
    count = 0
    for star in collection.find(filter_criteria):
        count += 1
        ra_J2016 = star.get('ra')
        dec_J2016 = star.get('dec')
        pmra = star.get('pmra')
        pmdec = star.get('pmdec')
        parallax = star.get('parallax')

        if None not in (ra_J2016, dec_J2016, pmra, pmdec, parallax):
            ra_J2000, dec_J2000 = convert_coordinates_with_proper_motion(
                ra_J2016, dec_J2016, pm_ra_cosdec=pmra, pm_dec=pmdec, parallax=parallax, reference_epoch='J2016'
            )
            try:
                collection.update_one({'_id': star['_id']},
                                      {'$set': {'ra_J2000': ra_J2000, 'dec_J2000': dec_J2000, 'CalculatedJ2000': True}})
            except PyMongoError as error:
                print(f"Error updating document ID {star['_id']}: {error}")

        if count % 10000 == 0:
            print(f"Procesado {count} registros en {threading.current_thread().name}. Velocidad por hilo: {count / (time.time() - start_time)} registros por segundo.")

    print(f"Hilo {threading.current_thread().name} completado. {count} registros procesados en {time.time() - start_time} segundos.")

num_threads = 2
threads = []
max_source_id = collection.count_documents({})
rango = max_source_id // num_threads

for i in range(num_threads):
    filter_criteria = {"_id": {"$gte": i * rango, "$lt": (i + 1) * rango}}
    thread = threading.Thread(target=process_subset, args=(filter_criteria,), name=f"Thread_{i}")
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

print("Procesamiento total completado.")
