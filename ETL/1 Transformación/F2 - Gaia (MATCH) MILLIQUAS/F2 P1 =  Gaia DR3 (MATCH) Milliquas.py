
from units import *


def emparejar(toleranciaCoordenadas, toleranciaDistancia):
    # Tiempo de ejecución: Inicio
    start_time = timeit.default_timer()

    # Conecta a MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['TFM']

    # Obtiene las colecciones
    coll1 = db['F1:P3 -> MILLIQUAS con Distancia Renombrada']
    coll2 = db['F1:P1 -> Gaia DR3 + Gaia QsoC']


    # Crea la nueva colección
    coll3 = db['F2:P1 -> Gaia DR3 MATCH Milliquas']
    print('Borrando datos de la colección')
    coll3.delete_many({})

    # Obtiene todos los documentos
    print("Leyendo colecciones")

    docs1 = list(coll1.find())
    #docs2 = list(coll2.find()) No es necesario, se hace filtrado por íncide en la BBDD


    # Margen de collerancia
    tolCoordenadas = toleranciaCoordenadas
    tolDistancia = toleranciaDistancia

    # Contadores
    i = 0
    j = 0

    print("Iniciando proceso")

    # Itera sobre los documentos de la primera colección
    for doc1 in docs1:
        i = i + 1

        if i % 10000 == 0:
            print("Procesados: ", i)

        ra1 = doc1['Millq_RA']
        dec1 = doc1['Millq_DEC']
        dist1 = doc1['Millq_Distancia']


        # Itera sobre los documentos de la segunda colección Filtro por distancia. Importante existencia índice campos Gaia_Distancia
        docs2 = list(coll2.find( {'Gaia_Distancia': { '$gt': dist1 - tolDistancia, '$lt': dist1 + tolDistancia } }) )

        # Incializar lista vacia para condidatos por tolerancia.
        valid_docs = []

        for doc2 in docs2:

            ra2 = doc2['Gaia_ra_J2000']
            dec2 = doc2['Gaia_dec_J2000']

            # Comprueba si las coordenadas están dentro del margen de tolerancia
            if math.isclose(ra1, ra2, abs_tol=tolCoordenadas) and math.isclose(dec1, dec2, abs_tol=tolCoordenadas):
                valid_docs.append(doc2)

        # Si hay documentos que cumplen el criterio, seleccionar el más cercano
        if valid_docs:
            j = j + 1

            # Seleccionar el más cercano a 0
            closest_doc = min(valid_docs, key=lambda d: abs(ra1 - d['Gaia_ra_J2000']) + abs(dec1 - d['Gaia_dec_J2000']))

            # Eliminar los campos _id (clave primarias)
            doc1.pop('_id', None)
            closest_doc.pop('_id', None)

            # Calcular la distancia valorabsoluto(ra1  - ra2) + valor absoluto(dec1 - dec2)
            total_diff_match = abs(ra1 - closest_doc['Gaia_ra_J2000']) + abs(dec1 - closest_doc['Gaia_dec_J2000'])

            # Combina los datos de ambos documentos
            combined_doc = {**doc1, **closest_doc, "total_diff_match": total_diff_match}

            # Inserta el documento combinado en la nueva colección
            coll3.insert_one(combined_doc)

        if j % 1000 == 0 and i>0:
            print("   Total: ", i, "   Encontrados: ", j, "   %: ", round( (j / i) * 100, 2) )

    print("Total: ", i, "   Encontrados: ", j, "   %: ", round( (j/i) *100, 2) )

    # Tiempo de ejecución: Fin
    end_time = timeit.default_timer()
    execution_time = round(end_time - start_time)
    print(f"El tiempo de ejecución fue: {execution_time} segundos")

    # Calcular estadísticas descriptivas del emparejamiento
    cursor = coll3.find({}, {"total_diff_match": 1, "_id": 0})
    df = pd.DataFrame(list(cursor))
    descriptives = df['total_diff_match'].describe()
    print(descriptives)

    # Visualizar la distribución
    plt.figure(figsize=(10, 6))
    sns.histplot(df['total_diff_match'], kde=True, stat='density')
    sns.kdeplot(df['total_diff_match'], color='red')
    plt.title('Distribución de total_diff_match')
    plt.show()



emparejar (0.000075, 1000)