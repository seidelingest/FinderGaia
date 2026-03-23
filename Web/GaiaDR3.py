import io
from flask import Flask, render_template_string, send_file, jsonify
import math
from astroquery.jplhorizons import Horizons
from datetime import datetime, timedelta  # Asegúrate de que timedelta esté importado
from numpy.polynomial.hermite import hermval
from pymongo import MongoClient
from flask import render_template, request, Flask
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.resources import INLINE
from bokeh.models import ColumnDataSource, Span, Label, WheelZoomTool
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from pymongo import MongoClient
from datetime import datetime
from waitress import serve  # Ensure waitress's serve is imported
from astroquery.simbad import Simbad
from bokeh.models import ColumnDataSource, Span, Label, WheelZoomTool

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']

def log_event(req, description):
    if req.headers.getlist("X-Forwarded-For"):
        client_ip = req.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = req.remote_addr
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"{current_time}" + " | " + f"{client_ip}" + " | " + f"{description}")
    # Crear un diccionario con la información del evento
    event = {
        "timestamp": current_time,
        "ip_address": client_ip,
        "description": description
    }

    # Insertar el evento en la colección "eventos"
    db['Evento'].insert_one(event)

    print(f"{current_time} | {client_ip} | {description}")


def hms_to_decimal(ra_str):
    """Convierte RA de horas minutos segundos a grados decimales"""
    ra_parts = list(map(float, ra_str.split()))
    return (ra_parts[0] + ra_parts[1] / 60 + ra_parts[2] / 3600) * 15  # Convierte horas a grados

def dms_to_decimal(dec_str):
    """Convierte DEC de grados minutos segundos a grados decimales"""
    dec_parts = list(map(float, dec_str.split()))
    sign = -1 if dec_parts[0] < 0 else 1
    return sign * (abs(dec_parts[0]) + dec_parts[1] / 60 + dec_parts[2] / 3600)


def planck(wavelength, temperature):
    h = 6.626e-34  # Planck's constant (J·s)
    c = 3.0e8  # Speed of light (m/s)
    k = 1.38e-23  # Boltzmann constant (J/K)
    wavelength_m = wavelength * 1e-9  # Convert wavelength to meters
    spectral_radiance = (2 * h * c ** 2) / (wavelength_m ** 5 * (np.exp((h * c) / (wavelength_m * k * temperature)) - 1))
    return spectral_radiance

def identify_spectral_lines(wavelengths, flux, threshold_ratio=0.005, distance=6):
    max_flux = max(flux)
    threshold = max_flux * threshold_ratio

    # Suavizar el flujo para detectar valles
    #flux = savgol_filter(flux, 11, 3)

    # Detectar picos (líneas de emisión)
    peaks, _ = find_peaks(flux, height=threshold, distance=distance)
    emission_lines = wavelengths[peaks]
    emission_intensities = flux[peaks]

    # Detectar valles (líneas de absorción)
    valleys, _ = find_peaks(-flux+max(flux+0.0001), height=threshold, distance=distance)
    absorption_lines = wavelengths[valleys]
    absorption_intensities = flux[valleys]

    return {
        "emission": {"wavelengths": emission_lines, "intensities": emission_intensities},
        "absorption": {"wavelengths": absorption_lines, "intensities": absorption_intensities}
    }

spectral_lines = {
    # Hidrógeno (H)
    'H_alpha': 656.28,
    'H_beta': 486.13,
    'H_gamma': 434.05,
    'H_delta': 410.17,
    'Lyman_alpha': 121.6,
    'Lyman_beta': 102.6,
    'Lyman_gamma': 97.3,
    'Paschen_alpha': 1875.1,
    'Paschen_beta': 1282.2,
    'Paschen_gamma': 1093.8,

    # Helio (He)
    'He_I_388.9': 388.9,
    'He_I_447.1': 447.1,
    'He_I_501.6': 501.6,
    'He_I_587.6': 587.6,
    'He_I_667.8': 667.8,
    'He_I_706.5': 706.5,
    'He_I_728.1': 728.1,
    'He_II_164.0': 164.0,
    'He_II_468.6': 468.6,
    'He_II_541.2': 541.2,
    'He_II_656.0': 656.0,

    # Carbono (C)
    'C_I_156.1': 156.1,
    'C_I_165.7': 165.7,
    'C_I_193.1': 193.1,
    'C_I_247.8': 247.8,
    'C_I_833.5': 833.5,
    'C_I_872.7': 872.7,
    'C_I_940.6': 940.6,
    'C_II_133.5': 133.5,
    'C_II_133.6': 133.6,
    'C_II_232.6': 232.6,
    'C_II_283.7': 283.7,
    'C_III_190.9': 190.9,
    'C_III_229.7': 229.7,
    'C_III_386.1': 386.1,
    'C_III_418.7': 418.7,

    # Oxígeno (O)
    'O_I_130.2': 130.2,
    'O_I_130.4': 130.4,
    'O_I_130.6': 130.6,
    'O_I_135.6': 135.6,
    'O_I_777.2': 777.2,
    'O_I_844.6': 844.6,
    'O_II_247.0': 247.0,
    'O_II_247.1': 247.1,
    'O_II_372.6': 372.6,
    'O_II_372.7': 372.7,
    'O_III_166.5': 166.5,
    'O_III_232.8': 232.8,
    'O_III_305.9': 305.9,
    'O_III_375.8': 375.8,

    # Nitrógeno (N)
    'N_I_174.3': 174.3,
    'N_I_141.1': 141.1,
    'N_I_149.3': 149.3,
    'N_II_108.5': 108.5,
    'N_II_108.7': 108.7,
    'N_II_399.5': 399.5,
    'N_II_403.5': 403.5,
    'N_III_175.6': 175.6,
    'N_III_464.0': 464.0,
    'N_III_486.7': 486.7,
    'N_III_492.3': 492.3,

    # Hierro (Fe)
    'Fe_I_372.0': 372.0,
    'Fe_I_374.5': 374.5,
    'Fe_I_381.6': 381.6,
    'Fe_I_388.6': 388.6,
    'Fe_I_400.5': 400.5,
    'Fe_I_404.6': 404.6,
    'Fe_I_406.3': 406.3,
    'Fe_I_413.2': 413.2,
    'Fe_I_423.3': 423.3,
    'Fe_I_430.8': 430.8,
    'Fe_I_438.4': 438.4,
    'Fe_I_440.4': 440.4,
    'Fe_I_442.7': 442.7,
    'Fe_I_444.8': 444.8,
    'Fe_I_447.6': 447.6,
    'Fe_I_448.1': 448.1,
    'Fe_I_449.4': 449.4,
    'Fe_I_452.8': 452.8,
    'Fe_I_457.5': 457.5,
    'Fe_I_466.8': 466.8,
    'Fe_I_495.7': 495.7,
    'Fe_I_516.7': 516.7,
    'Fe_II_234.0': 234.0,
    'Fe_II_237.4': 237.4,
    'Fe_II_238.2': 238.2,
    'Fe_II_258.6': 258.6,
    'Fe_II_259.9': 259.9,
    'Fe_II_492.4': 492.4,
    'Fe_II_501.8': 501.8,

    # Calcio (Ca)
    'Ca_I_422.7': 422.7,
    'Ca_I_443.5': 443.5,
    'Ca_I_445.5': 445.5,
    'Ca_I_526.2': 526.2,
    'Ca_I_559.8': 559.8,
    'Ca_I_616.2': 616.2,
    'Ca_I_643.9': 643.9,
    'Ca_II_393.4': 393.4,  # K line
    'Ca_II_396.8': 396.8,  # H line
    'Ca_II_849.8': 849.8,
    'Ca_II_854.2': 854.2,
    'Ca_II_866.2': 866.2,

    # Sodio (Na)
    'Na_I_330.2': 330.2,
    'Na_I_589.0': 589.0,  # D2 line
    'Na_I_589.6': 589.6,  # D1 line

    # Magnesio (Mg)
    'Mg_I_285.2': 285.2,
    'Mg_I_383.8': 383.8,
    'Mg_I_517.2': 517.2,
    'Mg_II_279.6': 279.6,
    'Mg_II_280.4': 280.4,
    'Mg_II_448.1': 448.1,

    # Titanio (Ti)
    'Ti_I_365.3': 365.3,
    'Ti_I_375.9': 375.9,
    'Ti_I_398.3': 398.3,
    'Ti_I_398.7': 398.7,
    'Ti_I_499.1': 499.1,
    'Ti_I_499.9': 499.9,
    'Ti_I_500.7': 500.7,
    'Ti_II_338.4': 338.4,
    'Ti_II_344.0': 344.0,
    'Ti_II_368.5': 368.5,
    'Ti_II_375.9': 375.9,
    'Ti_II_455.0': 455.0,
    'Ti_II_456.3': 456.3,
    'Ti_II_457.1': 457.1,

    # Níquel (Ni)
    'Ni_I_351.5': 351.5,
    'Ni_I_352.4': 352.4,
    'Ni_I_356.6': 356.6,
    'Ni_I_361.9': 361.9,
    'Ni_I_378.3': 378.3,
    'Ni_I_385.8': 385.8,
    'Ni_I_447.0': 447.0,

    # Cobre (Cu)
    'Cu_I_324.8': 324.8,
    'Cu_I_327.4': 327.4,
    'Cu_II_135.8': 135.8,
    'Cu_II_146.0': 146.0,

    # Zinc (Zn)
    'Zn_I_213.9': 213.9,
    'Zn_I_307.6': 307.6,

    # Aluminio (Al)
    'Al_I_396.2': 396.2,
    'Al_I_394.4': 394.4,
    'Al_II_167.0': 167.0,
    'Al_II_226.4': 226.4,
}


def decimal_to_equatorial(ra=None, dec=None):
    result = {}
    if ra is not None:
        ra_hours = int(ra // 15)
        ra_minutes = int((ra % 15) * 4)
        ra_seconds = round((((ra % 15) * 4) - ra_minutes) * 60, 2)
        result['ra_hours'] = ra_hours
        result['ra_minutes'] = ra_minutes
        result['ra_seconds'] = ra_seconds

    if dec is not None:
        dec_degrees = int(dec)
        dec_fractional = abs(dec - dec_degrees)
        dec_minutes = int(dec_fractional * 60)
        dec_seconds = round((dec_fractional * 60 - dec_minutes) * 60, 2)
        if dec < 0:
            dec_degrees = dec_degrees  # Maintain the negative sign
        result['dec_degrees'] = dec_degrees
        result['dec_minutes'] = dec_minutes
        result['dec_seconds'] = dec_seconds

    return result


@app.route('/plot_sampled_spectrum/<doc_id>', methods=['GET'])
def plot_sampled_spectrum(doc_id=None):
    doc_id = int(doc_id)
    db = MongoClient('mongodb://localhost:27017/')['TFM']

    current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one({"GaiaSpec_Source_id": doc_id})
    if not current_doc:
        return "Documento no encontrado", 404

    serie = pd.Series(range(336, 1021, 2))
    df = pd.DataFrame([current_doc])
    flux_value = np.array(df['GaiaSpec_flux'].iloc[0])
    flux_value_error = np.array(df['GaiaSpec_flux_error'].iloc[0])
    try:
        temp_efectiva = df['Gaia_teff_gspphot'].iloc[0]
    except KeyError:
        return "Temperatura efectiva no encontrada en el documento", 404

    black_body_spectrum = planck(serie, temp_efectiva)
    max_flux = max(flux_value)
    max_black_body = max(black_body_spectrum)
    normalization_factor = max_flux / max_black_body
    normalized_black_body_spectrum = black_body_spectrum * normalization_factor

    # Suavizar los valores de flujo
    smoothed_flux = savgol_filter(flux_value, 5, 4)

    detected_lines = identify_spectral_lines(serie.values, flux_value)
    source_id_value = current_doc['GaiaSpec_Source_id']

    log_event(request, 'Espectro -> Mostrar -> ' + str(current_doc['GaiaSpec_Source_id']))
    title_str = f"Espectrometría del objeto source_id = {source_id_value}"
    p = figure(title=title_str, x_axis_label='Longitud de onda en nm', y_axis_label='Flujo', sizing_mode='stretch_both',
               tools="pan,box_zoom,reset,save")  # Agrega las herramientas necesarias
    p.add_tools(WheelZoomTool())  # Añade la herramienta WheelZoomTool
    p.toolbar.active_scroll = p.select_one(WheelZoomTool)  # Activa WheelZoomTool

    p.scatter(serie, flux_value, alpha=1, marker='o', size=6, legend_label="Flujo")
    p.scatter(serie, flux_value_error, alpha=1, marker='o', size=3, color='green', legend_label="Error")
    p.line(serie, smoothed_flux, line_width=2, color='blue', legend_label="Curva Suavizada")
    p.line(serie, normalized_black_body_spectrum, line_width=2, color='red', legend_label=f"Planck (T={round(temp_efectiva, 0)} ºK)")

    # Crear las líneas de emisión y absorción para la leyenda
    emission_lines_source = ColumnDataSource(data=dict(base=detected_lines['emission']['wavelengths'], top=detected_lines['emission']['intensities']))
    absorption_lines_source = ColumnDataSource(data=dict(base=detected_lines['absorption']['wavelengths'], top=detected_lines['absorption']['intensities']))
    p.multi_line(xs=[[x, x] for x in detected_lines['emission']['wavelengths']],
                 ys=[[0, y] for y in detected_lines['emission']['intensities']],
                 line_width=1, color='blue', legend_label="Emisión")
    p.multi_line(xs=[[x, x] for x in detected_lines['absorption']['wavelengths']],
                 ys=[[0, y] for y in detected_lines['absorption']['intensities']],
                 line_width=1, color='orange', legend_label="Absorción")

    # Agregar etiquetas para las líneas de emisión detectadas
    for wavelength, intensity in zip(detected_lines['emission']['wavelengths'], detected_lines['emission']['intensities']):
        label_text = f"Emisión ({round(wavelength)})"
        label = Label(x=wavelength, y=intensity * 0.95, text=label_text, text_font_size='8pt', text_color='black',
                      angle=90, angle_units='deg', text_baseline='middle', text_align='center')
        p.add_layout(label)

    # Agregar etiquetas para las líneas de absorción detectadas
    for wavelength, intensity in zip(detected_lines['absorption']['wavelengths'], detected_lines['absorption']['intensities']):
        label_text = f"Absorción ({round(wavelength)})"
        label = Label(x=wavelength, y=intensity * 0.95, text=label_text, text_font_size='8pt', text_color='black',
                      angle=90, angle_units='deg', text_baseline='middle', text_align='center')
        p.add_layout(label)

    # Filtrar y agregar las líneas espectrales que están cerca de un punto de emisión o absorción
    close_lines = {}
    tolerance = 1  # Tolerancia en nm para considerar una línea cercana a un pico
    for line_name, wavelength in spectral_lines.items():
        is_close_to_emission = any(abs(wavelength - em_wl) < tolerance for em_wl in detected_lines['emission']['wavelengths'])
        is_close_to_absorption = any(abs(wavelength - abs_wl) < tolerance for abs_wl in detected_lines['absorption']['wavelengths'])
        if is_close_to_emission or is_close_to_absorption:
            close_lines[line_name] = wavelength

    # Añadir puntos verdes para las líneas espectrales filtradas
    spectral_indices = [np.argmin(np.abs(serie - wl)) for wl in close_lines.values()]
    spectral_flux_values = flux_value[spectral_indices]

    spectral_points_source = ColumnDataSource(data=dict(x=list(close_lines.values()), y=spectral_flux_values))
    p.scatter('x', 'y', source=spectral_points_source, color='green', size=10, marker='circle', legend_label="Líneas Espectrales")

    # Agregar etiquetas para las líneas espectrales filtradas en orientación vertical y con color negro
    for line_name, wavelength in close_lines.items():
        index = np.argmin(np.abs(serie - wavelength))
        label_text = f"{line_name} ({round(wavelength)})"
        label = Label(x=wavelength, y=flux_value[index] * 1.02, text=label_text, text_font_size='8pt', text_color='black',
                      angle=90, angle_units='deg', text_baseline='middle', text_align='center')
        p.add_layout(label)

    p.legend.location = 'top_right'
    p.legend.label_text_font_size = '8pt'

    script, div = components(p)
    resources = INLINE.render()
    return render_template('GraficoSpectroSimple.html', script=script, div=div, resources=resources, current_doc=current_doc)


@app.route('/plot_continuous_spectrum/<int:source_id>', methods=['GET'])
def plot_continuous_spectrum(source_id):
    # Conectar con la base de datos
    db = MongoClient('mongodb://localhost:27017/')['TFM']
    spectrum_data = db['Gaia DR3 XP Continuos Mean Spectrum'].find_one({"source_id": source_id})

    if not spectrum_data:
        return "Espectro continuo no encontrado", 404

    # Obtener los primeros 55 coeficientes para BP y RP
    bp_coefficients = spectrum_data['bp_coefficients'][:55]
    rp_coefficients = spectrum_data['rp_coefficients'][:55]

    # Parámetros de desplazamiento y escala para BP y RP
    delta_theta_bp = 30.00986
    theta_bp = 3.062231
    delta_theta_rp = 30.00292
    theta_rp = 3.020529

    # Definir los rangos de longitud de onda para BP y RP
    wavelengths_bp = np.linspace(330, 680, 1000)
    wavelengths_rp = np.linspace(640, 1000, 1000)

    # Reconstrucción del espectro BP y RP aplicando el desplazamiento y el factor de escala
    bp_spectrum = sum(
        c * hermite(n)((wavelengths_bp - delta_theta_bp) / theta_bp) for n, c in enumerate(bp_coefficients))
    rp_spectrum = sum(
        c * hermite(n)((wavelengths_rp - delta_theta_rp) / theta_rp) for n, c in enumerate(rp_coefficients))

    # Crear la gráfica con Bokeh
    p = figure(title=f"Espectro Continuo del objeto {source_id}", x_axis_label='Longitud de onda (nm)',
               y_axis_label='Flujo')
    p.line(wavelengths_bp, bp_spectrum, line_width=2, color='blue', legend_label="BP Spectrum")
    p.line(wavelengths_rp, rp_spectrum, line_width=2, color='red', legend_label="RP Spectrum")

    # Renderizar el gráfico en el template
    script, div = components(p)
    resources = INLINE.render()
    return render_template('GraficoSpectroContinuo.html', script=script, div=div, resources=resources)


@app.route('/download_csv/<int:doc_id>')
def download_csv(doc_id):
    db = MongoClient('mongodb://localhost:27017/')['TFM']
    current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one({"GaiaSpec_Source_id": doc_id})
    if not current_doc:
        return "Documento no encontrado", 404

    serie = range(336, 1021, 2)
    df = pd.DataFrame([current_doc])
    flux_value = df['GaiaSpec_flux'].iloc[0]
    flux_value_error = df['GaiaSpec_flux_error'].iloc[0]
    data = {'wavelength': serie, 'flux': flux_value, 'flux_error': flux_value_error}
    csv_df = pd.DataFrame(data)

    bytes_io = io.BytesIO()
    csv_df.to_csv(bytes_io, index=False, encoding='utf-8')
    bytes_io.seek(0)

    log_event(request, 'Descarga -> CSV -> ' + str(doc_id))
    return send_file(bytes_io, mimetype='text/csv', download_name=f'spectrum_{doc_id}.csv', as_attachment=True)

@app.route('/download_excel/<int:doc_id>')
def download_excel(doc_id):
    db = MongoClient('mongodb://localhost:27017/')['TFM']
    current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one({"GaiaSpec_Source_id": doc_id})
    if not current_doc:
        return "Documento no encontrado", 404

    serie = range(336, 1021, 2)
    df = pd.DataFrame([current_doc])
    flux_value = df['GaiaSpec_flux'].iloc[0]
    flux_value_error = df['GaiaSpec_flux_error'].iloc[0]
    data = {'wavelength': serie, 'flux': flux_value, 'flux_error': flux_value_error}
    excel_df = pd.DataFrame(data)

    bytes_io = io.BytesIO()
    with pd.ExcelWriter(bytes_io, engine='openpyxl') as writer:
        excel_df.to_excel(writer, index=False, sheet_name='Spectrum Data')
    bytes_io.seek(0)

    log_event(request, 'Descarga -> Excel -> ' + str(doc_id))
    return send_file(bytes_io, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download_name=f'spectrum_{doc_id}.xlsx', as_attachment=True)

@app.route('/download_json/<int:doc_id>')
def download_json(doc_id):
    db = MongoClient('mongodb://localhost:27017/')['TFM']
    current_doc = db['F3:P2 -> Gaia Spectrum (JOIN) Gaia DR3'].find_one({"GaiaSpec_Source_id": doc_id})
    if not current_doc:
        return "Documento no encontrado", 404

    serie = list(range(336, 1021, 2))
    flux_value = current_doc['GaiaSpec_flux']
    flux_value_error = current_doc['GaiaSpec_flux_error']
    data = {'wavelength': serie, 'flux': flux_value, 'flux_error': flux_value_error}

    log_event(request, 'Descarga -> JSON -> ' + str(doc_id))
    return jsonify(data)

import math
from datetime import datetime



def perform_geospatial_search(user_ra, user_dec, max_angular_distance, soloConEspectro, bp_rp_min=None, bp_rp_max=None,
                              mag_g_min=None, mag_g_max=None, teff_min=None, teff_max=None):
    def calculate_angular_distance(ra1, dec1, ra2, dec2):
        ra1, dec1, ra2, dec2 = map(math.radians, [ra1, dec1, ra2, dec2])
        sin_dec1, cos_dec1 = math.sin(dec1), math.cos(dec1)
        sin_dec2, cos_dec2 = math.sin(dec2), math.cos(dec2)
        delta_ra = ra2 - ra1
        cos_delta_ra = math.cos(delta_ra)

        # Asegurarse de que el valor esté entre -1 y 1
        value = sin_dec1 * sin_dec2 + cos_dec1 * cos_dec2 * cos_delta_ra
        value = max(-1, min(1, value))

        return math.acos(value)

    def adjust_dec_range(dec, max_distance):
        if dec - max_distance < -90:
            dec_min = -90
        else:
            dec_min = dec - max_distance

        if dec + max_distance > 90:
            dec_max = 90
        else:
            dec_max = dec + max_distance

        return dec_min, dec_max

    def adjust_ra_range(ra, max_distance):
        ra_min = ra - max_distance
        ra_max = ra + max_distance

        if ra_min < 0:
            ra_min += 360
        if ra_max >= 360:
            ra_max -= 360

        return ra_min, ra_max

    start_time = datetime.now()

    # Ajuste inicial de rangos de RA y DEC
    dec_range_min, dec_range_max = adjust_dec_range(user_dec, max_angular_distance)
    ra_range_min, ra_range_max = adjust_ra_range(user_ra, max_angular_distance)

    # Filtro inicial por rango de RA y DEC
    if ra_range_min > ra_range_max:
        query = {
            'dec_J2000': {'$gte': dec_range_min, '$lte': dec_range_max},
            '$or': [
                {'ra_J2000': {'$gte': ra_range_min}},
                {'ra_J2000': {'$lte': ra_range_max}}
            ]
        }
    else:
        query = {
            'ra_J2000': {'$gte': ra_range_min, '$lte': ra_range_max},
            'dec_J2000': {'$gte': dec_range_min, '$lte': dec_range_max}
        }

    # Aplicar filtros adicionales opcionales
    if soloConEspectro:
        query['has_xp_sampled'] = True
    if bp_rp_min is not None:
        query['bp_rp'] = {'$gte': float(bp_rp_min)}
    if bp_rp_max is not None:
        if 'bp_rp' in query:
            query['bp_rp']['$lte'] = float(bp_rp_max)
        else:
            query['bp_rp'] = {'$lte': float(bp_rp_max)}
    if mag_g_min is not None:
        query['phot_g_mean_mag'] = {'$gte': float(mag_g_min)}
    if mag_g_max is not None:
        if 'phot_g_mean_mag' in query:
            query['phot_g_mean_mag']['$lte'] = float(mag_g_max)
        else:
            query['phot_g_mean_mag'] = {'$lte': float(mag_g_max)}
    if teff_min is not None:
        query['teff_gspphot'] = {'$gte': float(teff_min)}
    if teff_max is not None:
        if 'teff_gspphot' in query:
            query['teff_gspphot']['$lte'] = float(teff_max)
        else:
            query['teff_gspphot'] = {'$lte': float(teff_max)}

    # Buscar en la base de datos de Gaia DR3
    results = db['Gaia DR3'].find(query)
    results_with_distance = []

    # Verificación de distancia esférica
    for result in results:
        ra, dec = result['ra_J2000'], result['dec_J2000']
        distance = calculate_angular_distance(user_ra, user_dec, ra, dec)
        distance_degrees = math.degrees(distance)

        if distance_degrees <= max_angular_distance:
            # Formateo de coordenadas a formato de cadena
            ra_str = decimal_to_equatorial(ra=ra)
            dec_str = decimal_to_equatorial(dec=dec)
            result['ra_J2000_Str'] = f"{ra_str['ra_hours']}h {ra_str['ra_minutes']}m {ra_str['ra_seconds']:.2f}s"
            result['dec_J2000_Str'] = f"{dec_str['dec_degrees']}° {dec_str['dec_minutes']}\' {dec_str['dec_seconds']:.2f}\""

            # Convertir los campos numéricos a flotantes
            numeric_fields = [
                'teff_gspphot', 'phot_g_mean_mag', 'bp_rp', 'phot_bp_mean_mag',
                'phot_rp_mean_mag', 'classprob_dsc_combmod_quasar',
                'classprob_dsc_combmod_galaxy', 'classprob_dsc_combmod_star',
                'distance_gspphot', 'parallax'
            ]
            for field in numeric_fields:
                if field in result and result[field] is not None:
                    result[field] = float(result[field])

            star_prob = result.get('classprob_dsc_combmod_star') or 0
            galaxy_prob = result.get('classprob_dsc_combmod_galaxy') or 0
            quasar_prob = result.get('classprob_dsc_combmod_quasar') or 0

            max_prob_field = 'classprob_dsc_combmod_star'
            max_prob = star_prob

            if galaxy_prob > max_prob:
                max_prob_field = 'classprob_dsc_combmod_galaxy'
                max_prob = galaxy_prob

            if quasar_prob > max_prob:
                max_prob_field = 'classprob_dsc_combmod_quasar'
                max_prob = quasar_prob

            star_prob = result.get('classprob_dsc_combmod_star') or 0
            galaxy_prob = result.get('classprob_dsc_combmod_galaxy') or 0
            quasar_prob = result.get('classprob_dsc_combmod_quasar') or 0

            max_prob_field = 'classprob_dsc_combmod_star'
            max_prob = star_prob

            if galaxy_prob > max_prob:
                max_prob_field = 'classprob_dsc_combmod_galaxy'
                max_prob = galaxy_prob

            if quasar_prob > max_prob:
                max_prob_field = 'classprob_dsc_combmod_quasar'
                max_prob = quasar_prob

            # Asignar el símbolo basado en el campo con mayor probabilidad
            symbol = 'circle'  # Por defecto, galaxy
            if max_prob_field == 'classprob_dsc_combmod_quasar':
                symbol = 'square'
            elif max_prob_field == 'classprob_dsc_combmod_star':
                symbol = 'cross'

            # Añadir resultado con la distancia, URL y símbolo
            result_with_distance = {
                'data': result,
                'distance': round(distance_degrees, 2),
                'urlSpectrumSampled': f"https://gaia.seidelingenieria.com:5002/plot_sampled_spectrum/{result['source_id']}",
                'urlSpectrumContinuos': f"https://gaia.seidelingenieria.com:5002/plot_continuos_spectrum/{result['source_id']}",
                'symbol': symbol,
            }
            results_with_distance.append(result_with_distance)

    # Ordenar los resultados por distancia
    sorted_results = sorted(results_with_distance, key=lambda x: x['distance'])

    end_time = datetime.now()
    execution_time = end_time - start_time
    log_event(request, 'Búsqueda espacial -> Terminada con tiempo -> ' + f"{execution_time.total_seconds()}" + ' con ' + str(len(sorted_results)) + ' objetos encontrados')

    return sorted_results



@app.route('/get_coordinates', methods=['POST'])
def get_coordinates():
    start_time = datetime.now()

    source_id = request.form.get('source_id', '').strip()
    if source_id:
        try:
            source_id = int(source_id)
            result = db['Gaia DR3'].find_one({"source_id": source_id})
            if result:
                ra = result['ra_J2000']
                dec = result['dec_J2000']
                ra_coords = decimal_to_equatorial(ra=ra)
                dec_coords = decimal_to_equatorial(dec=dec)
                log_event(request,
                          'Búsqueda de objeto por source_id ' + str(source_id) + 'AR: ' + str(ra_coords) + '- DEC: ' + str(dec_coords))
                return jsonify({
                    'ra_hours': ra_coords.get('ra_hours'),
                    'ra_minutes': ra_coords.get('ra_minutes'),
                    'ra_seconds': ra_coords.get('ra_seconds'),
                    'dec_degrees': dec_coords.get('dec_degrees'),
                    'dec_minutes': dec_coords.get('dec_minutes'),
                    'dec_seconds': dec_coords.get('dec_seconds')
                })
        except ValueError:
            pass

    end_time = datetime.now()
    execution_time = end_time - start_time
    log_event(request,
              'Búsqueda Coordenadas -> Source ID: ' + str(
                  source_id) + ' -> Terminada con tiempo -> ' + f"{execution_time.total_seconds()}" + ' -> Correcta')

    return jsonify({'error': 'Source ID no válido o no encontrado'}), 404


@app.route('/get_horizons_coordinates', methods=['POST'])
def get_horizons_coordinates():
    start_time = datetime.now()

    horizons_id = request.form.get('horizons_id', '').strip()
    if horizons_id:
        try:
            today = datetime.utcnow()
            tomorrow = today + timedelta(days=1)
            obj = Horizons(id=horizons_id, location='500', epochs={
                'start': today.strftime('%Y-%m-%d %H:%M:%S'),
                'stop': tomorrow.strftime('%Y-%m-%d %H:%M:%S'),
                'step': '1d'}).ephemerides()

            ra = obj['RA'][0]
            dec = obj['DEC'][0]

            # Ensure the declination captures the sign correctly
            if 'DEC' in obj.colnames:
                dec = obj['DEC'][0]
                if obj['DEC'][0] < 0:
                    dec = obj['DEC'][0]

            ra_coords = decimal_to_equatorial(ra=ra)
            dec_coords = decimal_to_equatorial(dec=dec)

            end_time = datetime.now()
            execution_time = end_time - start_time
            log_event(request,
                      'Búsqueda Coordenadas -> NASA/JPL: ' + str(horizons_id) + ' -> Terminada con tiempo -> ' + f"{execution_time.total_seconds()}" + ' -> Correcta')

            return jsonify({
                'ra_hours': ra_coords.get('ra_hours'),
                'ra_minutes': ra_coords.get('ra_minutes'),
                'ra_seconds': ra_coords.get('ra_seconds'),
                'dec_degrees': dec_coords.get('dec_degrees'),
                'dec_minutes': dec_coords.get('dec_minutes'),
                'dec_seconds': dec_coords.get('dec_seconds')
            })
        except Exception as e:
            log_event(request,
                      'Búsqueda NASA Horizons -> Objeto -> ' + str(horizons_id) + ' -> ' + ' -> Error: ' + str(e))
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Código NASA/Horizons JPL no válido o no encontrado'}), 404


@app.route('/get_simbad_coordinates', methods=['POST'])
def get_simbad_coordinates():
    start_time = datetime.now()

    hd_id = request.form.get('hd_id', '').strip()
    if hd_id:
        try:
            custom_simbad = Simbad()
            custom_simbad.add_votable_fields('ra', 'dec')
            result_table = custom_simbad.query_object(f'HD {hd_id}')
            if result_table is not None:
                ra_decimal = result_table['ra'][0]  # Ya en formato decimal
                dec_decimal = result_table['dec'][0]  # Ya en formato decimal

                # Convertir las coordenadas decimales a horas/minutos/segundos (RA) y grados/minutos/segundos (DEC)
                ra_coords = decimal_to_equatorial(ra=ra_decimal)
                dec_coords = decimal_to_equatorial(dec=dec_decimal)

                end_time = datetime.now()
                execution_time = end_time - start_time
                log_event(request,
                          'Búsqueda Coordenadas -> HD: ' + str(
                              hd_id) + ' -> Terminada con tiempo -> ' + f"{execution_time.total_seconds()}" + ' -> Correcta')

                return jsonify({
                    'ra_hours': ra_coords.get('ra_hours'),
                    'ra_minutes': ra_coords.get('ra_minutes'),
                    'ra_seconds': ra_coords.get('ra_seconds'),
                    'dec_degrees': dec_coords.get('dec_degrees'),
                    'dec_minutes': dec_coords.get('dec_minutes'),
                    'dec_seconds': dec_coords.get('dec_seconds')
                })
            else:
                return jsonify({'error': 'No se encontraron resultados en Simbad para el ID HD proporcionado'}), 404
        except Exception as e:
            log_event(request, f"Búsqueda SIMBAD -> Error: {str(e)}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'ID HD no válido o no encontrado'}), 404


# Función para convertir grados, minutos y segundos a grados decimales
def get_decimal_degrees(degrees, minutes, seconds):
    sign = 1 if degrees >= 0 else -1
    return sign * (abs(degrees) + minutes / 60.0 + seconds / 3600.0)


@app.route('/GaiaDR3', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        ra_hours = request.form.get('ra_hours', '').strip()
        ra_minutes = request.form.get('ra_minutes', '').strip()
        ra_seconds = request.form.get('ra_seconds', '').strip()
        dec_degrees = request.form.get('dec_degrees', '').strip()
        dec_minutes = request.form.get('dec_minutes', '').strip()
        dec_seconds = request.form.get('dec_seconds', '').strip()
        search_grados = request.form.get('search_degrees', '0.01').strip()
        bp_rp_min = request.form.get('bp_rp_min', '').strip()
        bp_rp_max = request.form.get('bp_rp_max', '').strip()
        mag_g_min = request.form.get('mag_g_min', '').strip()
        mag_g_max = request.form.get('mag_g_max', '').strip()
        teff_min = request.form.get('teff_min', '').strip()
        teff_max = request.form.get('teff_max', '').strip()

        results, num_results, execution_time = [], 0, 0

        if ra_hours and ra_minutes and ra_seconds and dec_degrees and dec_minutes and dec_seconds:
            ra_J2000 = (float(ra_hours) + (float(ra_minutes) / 60.0) + (float(ra_seconds) / 3600.0)) * 15.0
            dec_J2000 = get_decimal_degrees(float(dec_degrees), float(dec_minutes), float(dec_seconds))
            target_ra_dec = f"{ra_J2000} {dec_J2000}"
            search_grados = min(float(search_grados), 0.5)
            soloConEspectro = 'showSpectra' in request.form

            start_time = datetime.now()
            results = perform_geospatial_search(ra_J2000, dec_J2000, search_grados, soloConEspectro,
                                                bp_rp_min or None, bp_rp_max or None, mag_g_min or None, mag_g_max or None,
                                                teff_min or None, teff_max or None)

            for result in results:
                result['data'] = round_result_fields(result['data'])

            num_results = len(results)
            end_time = datetime.now()
            execution_time = end_time - start_time
        else:
            target_ra_dec = ""
            results = []
            num_results = 0
            execution_time = 0

        return render_template('GaiaDR3.html', results=results,
                               ra_hours=ra_hours, ra_minutes=ra_minutes, ra_seconds=ra_seconds,
                               dec_degrees=dec_degrees, dec_minutes=dec_minutes, dec_seconds=dec_seconds,
                               search_grados=search_grados, bp_rp_min=bp_rp_min, bp_rp_max=bp_rp_max,
                               mag_g_min=mag_g_min, mag_g_max=mag_g_max,
                               teff_min=teff_min, teff_max=teff_max,
                               num_results=num_results, execution_time=execution_time, target_ra_dec=target_ra_dec)

    log_event(request, "Iniciando -> web")
    return render_template('GaiaDR3.html', num_results=0, execution_time=0, target_ra_dec='')




def round_result_fields(result):
    fields_to_round = {
        'classprob_dsc_combmod_quasar': 3,
        'classprob_dsc_combmod_galaxy': 3,
        'classprob_dsc_combmod_star': 3,
        'teff_gspphot': 2,
        'phot_g_mean_mag': 2,
        'bp_rp': 3,
        'phot_bp_mean_mag': 2,
        'phot_rp_mean_mag': 2,
        'distance_gspphot': 1,
        'parallax': 4
    }
    for field, precision in fields_to_round.items():
        value = result.get(field)
        if value is not None:
            result[field] = round(value, precision)
    return result


if __name__ == '__main__':
    app.run(host='192.168.2.19', debug=True)
   #serve(app, host='192.168.200.80', port=5000)
