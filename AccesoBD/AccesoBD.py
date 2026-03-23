from units import *
import gc


def leerColeccion(coleccion):
    # Conexión a la BD
    client = MongoClient("127.0.0.1", 27017, maxPoolSize=100000)
    db = client.TFM  # Base de datos
    collection = db[coleccion]  # Colección
    client.close()

    return collection



def leerColeccionRegistros(coleccion):
    # Conexión a la BD
    collection = leerColeccion(coleccion)  # Colección
    cursorMaster = collection.find({})

    return cursorMaster



def leerColeccionPandas(coleccion, no_id=True):
    cursorMaster = leerColeccionRegistros(coleccion)

    clave = list(cursorMaster[0].keys()) #Útil para saber el campo clave del diccionario => pasarlo a lista

    df = pd.DataFrame(list(cursorMaster))

    if no_id:
        del df['_id']

    return(df)




def leerColeccionLista(coleccion):
    cursorMaster = leerColeccionRegistros(coleccion)

    clave = list(cursorMaster[0].keys()) #Útil para saber el campo clave del diccionario => pasarlo a lista

    data = [[0 for x in range(0)] for y in range(numColores)]

    l = 0  # estado de avance
    for doc in cursorMaster:
        # mostar información avance
        l = l + 1
        if (l % 10000) == 0:
            print(l)
        # añadir datos al array
        i = 0
        for key, val in doc.items():
            if key != '_id':
                data[i].append(val)
                i = i + 1

    return(data)



def leerColeccionNumpy(coleccion):
    cursorMaster = leerColeccionRegistros(coleccion)

    clave = list(cursorMaster[0].keys()) #Útil para saber el campo clave del diccionario => pasarlo a lista

    data = [[0 for x in range(0)] for y in range(numColores)]

    l = 0  # estado de avance
    for doc in cursorMaster:
        # mostar información avance
        l = l + 1
        if (l % 10000) == 0:
            print(l)
        # añadir datos al array
        i = 0
        for key, val in doc.items():
            if key != '_id':
                data[i].append(val)
                i = i + 1

    # Pasar a array de Numpy
    data_array = np.array(data)
    return(data_array)



def leerColeccionPandas(coleccion, no_id=True):
    cursorMaster = leerColeccionRegistros(coleccion)

    clave = list(cursorMaster[0].keys()) #Útil para saber el campo clave del diccionario => pasarlo a lista

    #data = [[0 for x in range(0)] for y in range(numColores)]
    df = pd.DataFrame(list(cursorMaster))

    if no_id:
        del df['_id']

    return(df)