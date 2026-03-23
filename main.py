import base64
from bson.binary import Binary

# Decodificar la cadena en base64
datos_decodificados = base64.b64decode('UiAgIA==')

# Imprimir los datos decodificados
print(datos_decodificados)

datos_binarios = Binary(base64.b64decode('UiAgIA=='))
print(datos_binarios)