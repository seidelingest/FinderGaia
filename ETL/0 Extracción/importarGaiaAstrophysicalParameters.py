import os
import gzip
import shutil
import pandas as pd
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor

# Conectar a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['TFM']
collection = db['Gaia DR3 AstrophysicalParameters']

print('Borrando datos de la colección')
collection.delete_many({})

# Directorio donde están los archivos .gz
directorio = 'E:\Catalogo\Gaia DR3\AstrophysicalParameters'


def procesar_archivo(archivo):
    # Comprobar si el archivo es un archivo .gz
    if archivo.endswith('.gz'):
        # Ruta completa al archivo .gz
        ruta_archivo_gz = os.path.join(directorio, archivo)
        # Ruta al archivo descomprimido (sin la extensión .gz)
        ruta_archivo_descomprimido = ruta_archivo_gz[:-3]

        # Abrir el archivo .gz y el archivo descomprimido
        with gzip.open(ruta_archivo_gz, 'rb') as f_in, open(ruta_archivo_descomprimido, 'wb') as f_out:
            print(ruta_archivo_gz + ' Descomprimiendo ')

            # Copiar el contenido del archivo .gz al archivo descomprimido
            shutil.copyfileobj(f_in, f_out)

        # Abre el archivo en modo de lectura y lee todas las líneas en una lista
        print(ruta_archivo_gz + ' Abriendo CSV en modo txt')
        with open(ruta_archivo_descomprimido, 'r') as f:
            lines = f.readlines()

        # Elimina las primeras 1541 líneas de la lista
        del lines[0:1541]

        # Abre el archivo en modo de escritura y escribe las líneas restantes al archivo
        print(ruta_archivo_gz+ ' Guardar CSV ')
        with open(ruta_archivo_descomprimido, 'w') as f:
            f.writelines(lines)

        # Leer el archivo descomprimido a partir de la línea 1542
        print(ruta_archivo_gz + ' Leyendo CSV Reducido')
        df = pd.read_csv(ruta_archivo_descomprimido, low_memory=False)

        # Insertar los datos en MongoDB
        print(ruta_archivo_gz + ' Insertando en BBDD')
        collection.insert_many(df.to_dict('records'))

    # Borrar el archivo descomprimido
    print(ruta_archivo_gz + ' Borrando Archivo ')
    os.remove(ruta_archivo_descomprimido)


# Crear un pool de hilos
with ThreadPoolExecutor(max_workers=2) as executor:
    # Recorrer todos los archivos en el directorio
    archivos = [archivo for archivo in os.listdir(directorio) if archivo.endswith('.gz')]
    # Enviar los archivos al pool de hilos para ser procesados
    executor.map(procesar_archivo, archivos)
