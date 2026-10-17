# Atlasvial: explorador por radio

Interfaz integrada a Flask en **http://127.0.0.1:5000/**. Conserva colores, tipografía y tarjetas: filtros a la izquierda, mapa principal y resultados a la derecha. No requiere Node ni servicios nuevos.

## Iniciar desde Windows CMD

Con Docker Desktop y MongoDB del proyecto disponibles:

```cmd
cd /d D:\Proyects\ParcialBigData
docker compose start --wait
scripts\start_ui.cmd
```

El script valida Compose, construye y ejecuta pytest, construye `parcialbigdata-api:ui-local`, recrea únicamente Flask y verifica salud/HTTP. No ejecuta ingesta ni Spark. La revisión OCI `working-tree-ui` identifica fuentes locales sin commit. Para reanudar el contenedor ya construido: `docker compose start --wait api`.

La interfaz sigue sin publicar. Un despliegue de Jenkins desde el código remoto anterior puede reemplazar esta imagen local. No se modifican Jenkinsfile, webhook ni credenciales.

## Utilizar y demostrar

1. Abrir la URL: aparece Estados Unidos, sin consultas automáticas de accidentes ni estadísticas.
2. Hacer clic en una ubicación: se rellenan coordenadas y se muestran centro/radio. También se pueden escribir latitud y longitud.
3. Ajustar el radio mediante slider o campo en metros (1–50.000). Elegir máximo 20, 50 o 100 accidentes; predeterminado 20.
4. Pulsar **Buscar accidentes**: se utiliza `/accidents/geo-near`, con distancias calculadas por MongoDB. Aparecen cantidad devuelta, marcadores por severidad y tarjetas con ID, ciudad/estado, fecha, severidad y distancia.
5. Seleccionar una tarjeta centra su marcador y abre detalles. Seleccionar un marcador abre su ventana y resalta la tarjeta. Documentos distintos pueden compartir coordenadas; sus tarjetas permiten abrir cada uno.
6. **Vista de Estados Unidos** recupera la vista general sin borrar selección ni resultados.

Ejemplo real: latitud **32.81517**, longitud **-116.914566**, radio **1000 m**, límite **20**: **8 accidentes**, incluido `A-44917` a 0 m. Con 5000 m se alcanza el límite 20 y se informa que existen más coincidencias. Estas cantidades corresponden a la muestra existente. Para mostrar ausencia de resultados: latitud 0, longitud 0, radio 1000.

Cambiar coordenadas/radio/límite cancela solicitudes pendientes y limpia resultados anteriores. Mover o ampliar el mapa no ejecuta consultas: se pulsa Buscar. La cantidad mostrada corresponde a los documentos devueltos, no al total ilimitado del área. Se distinguen carga, validación, error y ausencia de resultados.

## Alcance y límites

Se retiraron de la pantalla polígonos, hotspots, zonas de concentración, análisis temporal, gráficas, indicadores y navegación. **Se conservan** `/accidents/near`, `/accidents/within`, `/accidents/geo-near`, `/analytics`, cálculos y colecciones de Dask/Spark. No hay escrituras en la UI ni se descarga el millón de accidentes.

Leaflet 1.9.4 se sirve localmente. El fondo OpenStreetMap requiere Internet y conserva atribución; ante fallo queda un contorno local de EE. UU. con marcadores/consultas operativos. No se descargan teselas para uso offline. Los textos del dataset no se interpretan como HTML; no se envían credenciales al navegador.

En escritorio la página ocupa la altura de la ventana y los resultados desplazan dentro del panel. En pantallas pequeñas se apilan los paneles.

## Pruebas desde CMD

```cmd
call .venv\Scripts\activate.bat
python -m pytest tests tests_benchmark tests_ingestion -q
python scripts\smoke_geo.py http://127.0.0.1:5000
python -m pip install -r requirements\ui-test.txt
python -m playwright install chromium
python -m pytest tests_ui -q --junitxml=reports\ui-simplified\browser-final.xml
curl -f http://127.0.0.1:5000/health
curl -f "http://127.0.0.1:5000/accidents/geo-near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=20"
```

Las pruebas de navegador consultan datos reales; solo interceptan fallos de red/cancelación dentro del navegador de prueba. Bloquean teselas públicas para no cargar OpenStreetMap; el uso humano normal sí carga el fondo. Capturas/XML: `reports/ui-simplified/`, ignorado por Git. Pytest y el smoke UI permanecen integrados en los checks existentes de API. No se ejecuta un nuevo pipeline remoto sin publicar.
