from AccesoBD.AccesoBD import *
from units import *


def MostrarEspectro(Serie, Flux):
    # Crear el gráfico
    plt.figure(figsize=(8,6))
    plt.scatter(Serie, Flux[2], alpha=1, marker='.', s=10)
    #plt.xlim(360, 0)  # Para que el Este quede a la derecha
    plt.ylim(4E-17, 13E-17)  # Para que el Este quede a la derecha
    plt.grid(True)
    plt.title('Espectrometría')
    plt.xlabel('Frecuencia en nm')
    plt.ylabel('Flujo')
    plt.show()


print('Leyendo espectrometría')
df = leerColeccionPandas('Gaia DR3 XP Sampled Mean Spectrum', no_id=True)

MostrarEspectro(serieNanometros, df['flux'])



