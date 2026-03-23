from flask import Flask, render_template_string
from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import render_template
from bson.objectid import ObjectId
from flask import Flask, render_template_string, redirect, url_for, render_template, request
from pymongo import GEO2D
import math
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, FK5
from astropy.time import Time
from astropy import units as u
from pymongo import MongoClient
import numpy as np


import pandas as pd

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']

@app.route('/plot', methods=['GET'])
def redirect_to_first_plot():
    first_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one()
    if first_doc:
        return redirect(url_for('plot', doc_id=str(first_doc["_id"])))
    else:
        return "No hay documentos en la colección", 404


@app.route('/plot/<doc_id>', methods=['GET'])
def plot(doc_id=None):
    # Conectarse a la base de datos y colección
    db = MongoClient('mongodb://localhost:27017/')['TFM']

    # Si no se proporciona un doc_id, obtenemos el primer documento
    if doc_id is None:
        current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one()
    else:
        current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one({"_id": ObjectId(doc_id)})

    if not current_doc:
        return "Documento no encontrado", 404

    # Obtener el ID del documento anterior y siguiente
    prev_doc_cursor = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find({"_id": {"$lt": current_doc["_id"]}}).sort(
        [("_id", -1)]).limit(1)
    next_doc_cursor = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find({"_id": {"$gt": current_doc["_id"]}}).sort(
        [("_id", 1)]).limit(1)

    prev_doc = prev_doc_cursor[0] if prev_doc_cursor.count() > 0 else None
    next_doc = next_doc_cursor[0] if next_doc_cursor.count() > 0 else None

    prev_doc_id = str(prev_doc["_id"]) if prev_doc else None
    next_doc_id = str(next_doc["_id"]) if next_doc else None

    # Prepara tus datos para el gráfico
    serie = pd.Series(range(336, 1021, 2))
    df = pd.DataFrame([current_doc])
    flux_value = df['GaiaSpec_flux'].iloc[0]
    flux_value_error = df['GaiaSpec_flux_error'].iloc[0]

    # Crear el gráfico con Bokeh
    # Suponiendo que ya tienes el documento actual en la variable 'current_doc'
    source_id_value = current_doc['GaiaSpec_Source_id']

    # Construir el título completo
    # Crear el gráfico con Bokeh
    title_str = f"Espectrometría del objeto source_id = {source_id_value}"
    p = figure(title=title_str, x_axis_label='Longitud de onda en nm', y_axis_label='Flujo', width=1200, height=1000)

    # Añadir las series con sus respectivos títulos (leyendas)
    p.scatter(serie, flux_value, alpha=1, marker='.', size=10, legend_label="Flujo")
    p.scatter(serie, flux_value_error, alpha=1, marker='.', size=10, color='green', legend_label="Error")

    # Configurar la leyenda
    p.legend.location = 'top_left'
    p.legend.label_text_font_size = '12pt'  # Ajusta el tamaño de la fuente de la leyenda

    # Opcional: configurar la ubicación de la leyenda
    p.legend.location = 'top_left'

    # Embeber el gráfico en la página web
    script, div = components(p)
    resources = INLINE.render()

    return render_template('GraficoSpectroSimple.html', script=script, div=div, resources=resources, prev_doc_id=prev_doc_id,
                           next_doc_id=next_doc_id, current_doc=current_doc)



def perform_geospatial_search(user_ra, user_dec, max_angular_distance=0.02):
    # Conectar a la base de datos
    client = MongoClient('mongodb://localhost:27017/')
    db = client['TFM']

    # Función para calcular la distancia angular
    def calculate_angular_distance(ra1, dec1, ra2, dec2):
        # Convertir coordenadas de grados a radianes
        ra1, dec1, ra2, dec2 = map(math.radians, [ra1, dec1, ra2, dec2])

        # Calcula la distancia angular
        sin_dec1, cos_dec1 = math.sin(dec1), math.cos(dec1)
        sin_dec2, cos_dec2 = math.sin(dec2), math.cos(dec2)
        delta_ra = ra2 - ra1
        cos_delta_ra = math.cos(delta_ra)

        # Fórmula de distancia angular
        return math.acos(sin_dec1 * sin_dec2 + cos_dec1 * cos_dec2 * cos_delta_ra)

    # Calcular rangos para RA y DEC
    ra_min = max(0, user_ra - max_angular_distance)
    ra_max = min(360, user_ra + max_angular_distance)
    dec_min = max(-90, user_dec - max_angular_distance)
    dec_max = min(90, user_dec + max_angular_distance)

    # Realizar la consulta utilizando el índice
    query = {
        'GaiaSpec_ra': {'$gte': ra_min, '$lte': ra_max},
        'GaiaSpec_dec': {'$gte': dec_min, '$lte': dec_max}
    }
    results = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find(query).limit(1000)

    # Calcular la distancia angular y ordenar los resultados
    results_with_distance = []
    for result in results:
        ra, dec = result['GaiaSpec_ra'], result['GaiaSpec_dec']
        distance = calculate_angular_distance(user_ra, user_dec, ra, dec)
        distance_degrees = math.degrees(distance)
        if distance_degrees <= max_angular_distance:
            result_with_distance = {
                'data': result,
                'distance': distance_degrees,
                'url': f"http://nas00.seidelingenieria.com:5000/plot/{result['_id']}"  # URL del espectro
            }
            results_with_distance.append(result_with_distance)

    # Ordenar los resultados por distancia angular
    sorted_results = sorted(results_with_distance, key=lambda x: x['distance'])

    return sorted_results

def ra_to_decimal(hours, minutes, seconds):
    """ Convierte RA de formato h:m:s a grados decimales """
    return (hours + minutes / 60 + seconds / 3600) * 15

def dec_to_decimal(degrees, minutes, seconds):
    """ Convierte DEC de formato d:m:s a grados decimales """
    sign = 1 if degrees >= 0 else -1
    return degrees + sign * (minutes / 60 + seconds / 3600)


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        # Obtener y convertir RA y DEC
        ra_hours = float(request.form.get('ra_hours'))
        ra_minutes = float(request.form.get('ra_minutes'))
        ra_seconds = float(request.form.get('ra_seconds'))
        dec_degrees = float(request.form.get('dec_degrees'))
        dec_minutes = float(request.form.get('dec_minutes'))
        dec_seconds = float(request.form.get('dec_seconds'))

        # Convertir de J2000 a J2016 -> No es necesario
        user_ra, user_dec = convert_coordinates(ra_hours, ra_minutes, ra_seconds, dec_degrees, dec_minutes, dec_seconds)

        # Realizar la búsqueda geoespacial y obtener los resultados
        results = perform_geospatial_search(user_ra, user_dec)

        # Renderizar la plantilla de resultados de búsqueda
        return render_template('GaiaDR3.html', results=results)

    return render_template('GaiaDR3.html')



def convert_coordinates(ra_hours, ra_minutes, ra_seconds, dec_degrees, dec_minutes, dec_seconds):
    # Convertir RA de horas, minutos y segundos a grados decimales
    ra_J2000 = (ra_hours + (ra_minutes / 60.0) + (ra_seconds / 3600.0)) * 15.0

    # Convertir DEC de grados, minutos y segundos a grados decimales
    dec_J2000 = dec_degrees + (dec_minutes / 60.0) + (dec_seconds / 3600.0)

    # Crear un objeto SkyCoord con coordenadas J2000
    coord_J2000 = SkyCoord(ra_J2000 * u.deg, dec_J2000 * u.deg, frame='fk5', equinox='J2000')

    # Precesar las coordenadas a J2016
    coord_J2016 = coord_J2000.transform_to(FK5(equinox=Time('J2016')))

    #return coord_J2016.ra.deg, coord_J2016.dec.deg
    return ra_J2000, dec_J2000

if __name__ == '__main__':
    app.run(host='192.168.1.5', debug=True)


