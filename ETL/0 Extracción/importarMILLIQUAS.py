from units import *

# Esta función inserta una lisde de diccionarios en una colección de MongoBD. Permite especificar si borrar antes todos los registros.
def insertarRegistrosDesdeFileFITS(borrarRegistros, coleccion, rutaFITS, nombreCSV):
    print ('..\catalogos' + nombreCSV)
    # Tiempo de ejecución: Inicio
    start_time = timeit.default_timer()

    # Conexión a MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['TFM']  # Aquí va el nombre de tu base de datos
    collection = db[coleccion]  # Aquí va el nombre de tu colección

    # Abrir el archivo FITS
    hdul = fits.open(rutaFITS)  # Aquí va la ruta a tu archivo FITS

    # Ver datos del fichero
    hdul.info()

    # Asumiendo que los datos que quieres están en el primer HDU
    print('Accediendo a la capa del fichero FITS')
    hdu = hdul[1]
    data = hdu.data

    # Convertir los datos a un DataFrame de pandas
    print('Preparando los datos')
    df = pd.DataFrame(np.array(data))
    # Convertir los datos de tipo BinData a String
    df = df.applymap(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)
    # Eliminar espacios en blanco
    df.replace(r'\s', '', regex=True, inplace=True)
    # Convertir el DataFrame a una lista de diccionarios
    ListDict = df.to_dict('records')

    # Guardar los datos en un archivo CSV
    #df.to_csv('..\Catalogos' + nombreCSV, index=False)  # Aquí va la ruta a tu archivo CSV

    # Insertar los datos en MongoDB
    print('Insertando registros')
    if borrarRegistros == True:
        print('Borrando datos de la colección ' + coleccion)
        collection.delete_many({})
    collection.insert_many(ListDict)

    # Cerrar el archivo FITS
    hdul.close()

    # Tiempo de ejecución: Fin
    end_time = timeit.default_timer()
    execution_time = round(end_time - start_time)
    print(f"El tiempo de ejecución fue: {execution_time} segundos")


def InsertarRegistrosCatalogoGaia(borrarRegistros, coleccion, ruta):
    # Conectar a MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['TFM']
    collection = db[coleccion]

    if borrarRegistros == True:
        print('Borrando datos de la colección ' + coleccion)
        collection.delete_many({})

    # Directorio donde están los archivos .gz
    directorio = ruta

    # Recorrer todos los archivos en el directorio
    for archivo in os.listdir(directorio):
        # Comprobar si el archivo es un archivo .gz
        if archivo.endswith('.gz'):
            # Ruta completa al archivo .gz
            ruta_archivo_gz = os.path.join(directorio, archivo)
            # Ruta al archivo descomprimido (sin la extensión .gz)
            ruta_archivo_descomprimido = ruta_archivo_gz[:-3]

            # Abrir el archivo .gz y el archivo descomprimido
            with gzip.open(ruta_archivo_gz, 'rb') as f_in, open(ruta_archivo_descomprimido, 'wb') as f_out:
                print(ruta_archivo_gz)
                print(' Descomprimiendo ')

                # Copiar el contenido del archivo .gz al archivo descomprimido
                shutil.copyfileobj(f_in, f_out)


            # Abre el archivo en modo de lectura y lee todas las líneas en una lista
            print(' Abriendo CSV en modo txt')
            with open(ruta_archivo_descomprimido, 'r') as f:
                lines = f.readlines()

            # Elimina las primeras 1000 líneas de la lista
            del lines[0:1000]

            # Abre el archivo en modo de escritura y escribe las líneas restantes al archivo
            print(' Guardar CSV ')
            with open(ruta_archivo_descomprimido, 'w') as f:
                f.writelines(lines)


            # Leer el archivo descomprimido a partir de la línea 1001
            print(' Leyendo CSV Reducido')
            df = pd.read_csv(ruta_archivo_descomprimido)

            print (df)
            #print(df.to_dict('records'))

            # Insertar los datos en MongoDB
            print(' Insertando en BBDD')

            collection.insert_many(df.to_dict('records'))

        # Borrar el archivo descomprimido
        print(' Borrando Archivo ')
        os.remove(ruta_archivo_descomprimido)



#insertarRegistrosDesdeFileFITS( True, 'MILLIQUAS', '..\catalogos\milliquas.fits', '\MILLIQUAS.csv')
#insertarRegistrosDesdeFileFITS( True, 'MORX', '..\catalogos\MORX.fits', 'MORX.csv')

#InsertarRegistrosCatalogoGaia(True, 'Gaia DR3' ,'E:\Catalogo')