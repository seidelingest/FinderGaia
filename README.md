# GaiaFinder

Plataforma Big Data para exploración, consulta y visualización astronómica basada en el catálogo Gaia DR3 de la Agencia Espacial Europea (ESA).

## Descripción

GaiaFinder es una plataforma desarrollada para el almacenamiento, procesamiento y explotación eficiente de grandes volúmenes de datos astronómicos procedentes del catálogo Gaia DR3.

El proyecto integra procesos ETL optimizados, almacenamiento escalable en MongoDB, servicios API de alto rendimiento y una interfaz web interactiva orientada a la exploración científica de datos estelares.

El objetivo principal es permitir consultas espaciales y espectrales sobre cientos de millones de registros astronómicos manteniendo tiempos de respuesta reducidos.

---

# Características principales

* Procesamiento masivo de datos Gaia DR3
* Arquitectura Big Data escalable
* Pipeline ETL optimizado
* MongoDB como almacenamiento principal
* Consultas espaciales de alta velocidad
* Visualización espectral BP/RP
* API REST desarrollada en Flask
* Interfaz web interactiva
* Optimización mediante índices y particionado lógico
* Soporte para visualización astronómica

---

# Arquitectura del sistema

```text
Gaia DR3 Files
       |
       v
ETL Optimizado en Python
       |
       v
MongoDB
       |
       +------ API Flask
       |
       +------ Procesos analíticos
       |
       v
Frontend Web GaiaFinder
```

---

# Tecnologías utilizadas

## Backend

* Python
* Flask
* PyMongo
* NumPy
* Pandas

## Base de datos

* MongoDB
* Índices espaciales y optimización de consultas

## Frontend

* HTML5
* JavaScript
* Bootstrap
* Aladin Lite
* jQuery

## Infraestructura

* Linux / Windows Server
* Nginx
* OpenVPN

---

# Dataset utilizado

## Gaia DR3

El proyecto utiliza datos públicos del catálogo Gaia Data Release 3 (Gaia DR3), publicado por la Agencia Espacial Europea.

Incluye:

* Astrometría
* Fotometría
* Parámetros físicos estelares
* Espectros BP/RP de baja resolución
* Clasificación de objetos
* Distancias estimadas

Documentación oficial:

[https://www.cosmos.esa.int/web/gaia/dr3](https://www.cosmos.esa.int/web/gaia/dr3)

---

# Estructura general del proyecto

```text
FinderGaia/
│
├── API/
├── ETL/
├── Frontend/
├── Scripts/
├── MongoDB/
├── Documentacion/
└── README.md
```

---

# Pipeline ETL

El sistema ETL desarrollado permite:

* Lectura masiva de archivos comprimidos Gaia DR3
* Procesamiento en streaming
* Inserción por lotes
* Paralelización
* Recuperación ante fallos
* Optimización de memoria
* Compresión de comunicaciones MongoDB mediante zstd

El sistema está diseñado para trabajar con cientos de millones de registros.

---

# Optimización y rendimiento

El proyecto incorpora múltiples estrategias de optimización:

## Optimización de MongoDB

* Índices sobre campos astronómicos críticos
* Batching de inserciones
* Compresión zstd
* Cursor batch tuning
* Reintentos automáticos ante fallos de red
* Optimización de escritura masiva

## Optimización espacial

Las búsquedas espaciales utilizan:

* Bounding boxes
* Filtrado angular
* Reducción de espacio de búsqueda
* Colecciones derivadas especializadas

## Rendimiento observado

* Inserciones de decenas de miles de registros por segundo
* Consultas espaciales en tiempos reducidos
* Procesamiento de cientos de millones de objetos astronómicos

---

# API REST

La plataforma incluye una API desarrollada con Flask para acceso programático a los datos astronómicos.

## Funcionalidades principales

* Consultas espaciales
* Recuperación de espectros
* Búsquedas por source_id
* Filtros astronómicos
* Acceso a colecciones derivadas

Ejemplo:

```http
POST /GaiaDR3
```

---

# Plataforma web

GaiaFinder incluye una interfaz web para exploración visual de datos astronómicos.

## Funcionalidades

* Visualización de objetos estelares
* Exploración espectral BP/RP
* Integración con Aladin Lite
* Visualización interactiva
* Consultas espaciales en tiempo real

---

# Casos de uso

* Exploración astronómica
* Análisis de estructuras galácticas
* Estudios espectrales
* Visualización científica
* Investigación educativa
* Experimentación Big Data

---

# Instalación

## Requisitos

* Python 3.11+
* MongoDB 8+
* RAM elevada recomendada
* SSD recomendado

## Instalación de dependencias

```bash
pip install -r requirements.txt
```

## Ejecución de MongoDB

```bash
mongod
```

## Lanzamiento de la API

```bash
python app.py
```

---

# Despliegue

El sistema puede desplegarse:

* En entorno local
* En servidores dedicados
* En infraestructura cloud
* En arquitecturas distribuidas

La arquitectura está preparada para escalar horizontalmente.

---

# Capturas

## Plataforma web

*Añadir capturas de GaiaFinder*

## Visualización espectral

*Añadir capturas BP/RP*

## Arquitectura

*Añadir diagramas del sistema*

---

# Futuras mejoras

* Integración de clustering astronómico
* Escalado distribuido completo
* Incorporación de nuevos catálogos
* Motor de búsqueda avanzada
* Visualización 3D galáctica
* Integración IA/ML

---

# Autor

Esteban Fernández Mañanes

Ingeniería de Datos · Ciencia de Datos · Astrofísica

---

# Licencia

Proyecto desarrollado con fines académicos y de investigación.

Los datos astronómicos pertenecen a ESA Gaia Mission.

[https://www.cosmos.esa.int/gaia](https://www.cosmos.esa.int/gaia)
