import os
import gzip
import shutil
import pandas as pd
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor
import time

# Conectar a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3 XP Continuos Mean Spectrum']

#print('Borrando datos de la colección')
#collection.delete_many({})

# Directorio donde están los archivos .gz
directorio_comprimido = r'X:\GaiaDR3\Spectra\XpContinuousMeanSpectrum'

# Directorio donde se descomprimirán los archivos
directorio_descomprimido = r'C:\Users\Esteban\Desktop\BigData\TFM\Descomprimir'

# Asegurarse de que el directorio de descompresión exista
os.makedirs(directorio_descomprimido, exist_ok=True)

# Función para convertir la cadena a una lista de floats
def string_to_float_list(s):
    numbers = s.strip("[]").split(",")
    return [float(num) for num in numbers if num]

# Función para procesar cada archivo .gz
def procesar_archivo(archivo):
    try:
        # Comprobar si el archivo es un archivo .gz
        if archivo.endswith('.gz'):
            ruta_archivo_gz = os.path.join(directorio_comprimido, archivo)
            ruta_archivo_descomprimido = os.path.join(directorio_descomprimido, archivo[:-3])

            # Abrir el archivo .gz y descomprimirlo
            with gzip.open(ruta_archivo_gz, 'rb') as f_in, open(ruta_archivo_descomprimido, 'wb') as f_out:
                print(f'Descomprimiendo {ruta_archivo_gz} en {ruta_archivo_descomprimido}')
                shutil.copyfileobj(f_in, f_out)

            # Definir tipos de datos para columnas numéricas
            dtype_especificado = {
                'source_id': 'int64',
                'solution_id': 'int64',
                'bp_basis_function_id': 'int64',
                'bp_degrees_of_freedom': 'int64',
                'bp_n_parameters': 'int64',
                'bp_n_measurements': 'int64',
                'bp_n_rejected_measurements': 'int64',
                'bp_standard_deviation': 'float64',
                'bp_chi_squared': 'float64',
                'bp_coefficients': 'object',  # Convertido más tarde
                'bp_coefficient_errors': 'object',  # Convertido más tarde
                'bp_coefficient_correlations': 'object',  # Convertido más tarde
                'bp_n_relevant_bases': 'int64',
                'bp_relative_shrinking': 'float64',
                'rp_basis_function_id': 'int64',
                'rp_degrees_of_freedom': 'int64',
                'rp_n_parameters': 'int64',
                'rp_n_measurements': 'int64',
                'rp_n_rejected_measurements': 'int64',
                'rp_standard_deviation': 'float64',
                'rp_chi_squared': 'float64',
                'rp_coefficients': 'object',  # Convertido más tarde
                'rp_coefficient_errors': 'object',  # Convertido más tarde
                'rp_coefficient_correlations': 'object',  # Convertido más tarde
                'rp_n_relevant_bases': 'int64',
                'rp_relative_shrinking': 'float64'
            }

            # Leer el archivo CSV descomprimido a partir de la línea 183
            print(f'Leyendo CSV desde la línea 183: {ruta_archivo_descomprimido}')
            df = pd.read_csv(ruta_archivo_descomprimido, skiprows=182, delimiter=',', dtype=dtype_especificado, low_memory=False)

            # Aplicar la conversión a las columnas que contienen listas de flotantes
            columnas_a_convertir = ['bp_coefficients', 'bp_coefficient_errors', 'bp_coefficient_correlations',
                                    'rp_coefficients', 'rp_coefficient_errors', 'rp_coefficient_correlations']
            for columna in columnas_a_convertir:
                if columna in df.columns:
                    df[columna] = df[columna].apply(string_to_float_list)

            # Insertar cada fila como un documento en MongoDB
            registros = df.to_dict(orient='records')  # Convertir cada fila en un diccionario
            print(f'Insertando {len(registros)} registros en MongoDB')
            collection.insert_many(registros)  # Insertar los documentos

            # Borrar el archivo descomprimido después del procesamiento exitoso
            print(f'Borrando archivo descomprimido: {ruta_archivo_descomprimido}')
            os.remove(ruta_archivo_descomprimido)

    except Exception as e:
        print(f'Error procesando el archivo {archivo}: {e}')

# Procesamiento concurrente de archivos

def procesar_todos_los_archivos():
    #time.sleep(5 * 60 * 60)
    archivos = [archivo for archivo in os.listdir(directorio_comprimido) if archivo.endswith('.gz')]
    with ThreadPoolExecutor(max_workers=12) as executor:  # Puedes ajustar el número de workers
        executor.map(procesar_archivo, archivos)


procesar_todos_los_archivos()
