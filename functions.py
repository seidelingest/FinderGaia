from units import *
from pathlib import Path

def is_float(value):
  try:
    float(value)
    return True
  except:
    return False

def magnitudLineal(value):
  try:
    if is_float(value):
      return( round(value * pow(100, 0.2), 3) )
    else:
      return None
  except:
    return None


# Guarda la imagen de un plot. El parámetro ruta debe pasarse sin '\' inicial
def guardarPlot(ruta, plt, dpi):
  #ruta = ruta.replace('/', '-')
  ruta = ruta.replace(':', '-')
  ruta = ruta.replace('*', '-')
  ruta = ruta.replace('?', '-')
  ruta = ruta.replace('"', '-')
  ruta = ruta.replace('<', '-')
  ruta = ruta.replace('>', '-')
  ruta = ruta.replace('|', '-')

  script_dir = os.path.dirname(__file__)

  ruta = os.path.join(script_dir, ruta)

  if os.path.isfile(ruta):
    os.remove(ruta)
    print('Borrado de fichero existente')

  print (ruta)

  plt.savefig(ruta , bbox_inches='tight', dpi=dpi)

  return

