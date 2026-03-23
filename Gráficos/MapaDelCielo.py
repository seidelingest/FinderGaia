from AccesoBD.AccesoBD import *
from units import *


def MapaDelCielo(AR, DEC):
    # Crear el gráfico
    plt.figure(figsize=(8,6))
    plt.scatter(AR, DEC , alpha=0.5, marker='.', s=0.2)
    plt.xlim(360, 0)  # Para que el Este quede a la derecha
    plt.grid(True)
    plt.title('Ubicación de objetos astronómicos')
    plt.xlabel('Ascensión recta (grados)')
    plt.ylabel('Declinación (grados)')
    plt.show()


df = leerColeccionPandas('MILLIQUAS', no_id=True)
MapaDelCielo(df['RA'], df['DEC'])

df = leerColeccionPandas('MORX', no_id=True)
MapaDelCielo(df['RA'], df['DEC'])