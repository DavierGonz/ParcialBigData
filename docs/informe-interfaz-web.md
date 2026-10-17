# Atlasvial: entrega local simplificada

Interfaz activa en **http://127.0.0.1:5000/**. Se reutilizan Leaflet, los estilos, la marca y las tarjetas originales. Cambios locales en `feat/web-dashboard`, sin commits ni push.

## Cambios

Una sola pantalla: filtros por coordenadas/radio a la izquierda, mapa de Estados Unidos como elemento principal y resultados a la derecha. Se conservan selección por clic o escritura, centro/radio visibles, slider, límite predeterminado 20 (máximo 100), distancias reales, selección de tarjetas/marcadores, popups y Vista de Estados Unidos.

Se retiraron únicamente de la experiencia visual polígonos, hotspots, zonas de concentración, análisis temporal, gráficas, indicadores superiores y navegación. No se solicitan estadísticas al abrir la página. `/accidents/near`, `/accidents/within`, `/accidents/geo-near` y `/analytics` siguen operativos. La interfaz consulta `$geoNear` mediante el endpoint existente.

Cambiar filtros cancela consultas y limpia resultados anteriores. Se mantienen validación, mensajes de carga/error/ausencia de resultados y límites del backend. Los textos se insertan de forma segura. Desktop aprovecha la altura disponible sin desplazamiento vertical de página; la lista dispone de desplazamiento interno.

## Verificación real

| Comprobación | Resultado |
|---|---|
| Pytest local: tests, tests_benchmark, tests_ingestion | 85 aprobadas, 2 omitidas; 2,70 s |
| Suite API en Docker | 71 aprobadas; 0,42 s |
| Navegador Chromium sobre candidata | 19 aprobadas; 15,37 s |
| Navegador Chromium sobre puerto 5000 | 19 aprobadas; 15,00 s |
| HTTP integrado | HTML/recursos, near, geoNear, within, cinco tipos analíticos y validación aprobados |
| Escritorio | 1280×720, 1366×768, 1440×900 y 1920×1080 sin scroll vertical de página |
| Pantalla pequeña | 580×900 sin desbordamiento horizontal |

Las suites se solapan y no se suman como pruebas únicas. Las omisiones corresponden al bloqueo de caché Linux y a integración de ingesta Docker; no se repitió la ingesta. Las pruebas del navegador consultan datos reales y bloquean teselas públicas; el fondo se carga normalmente durante uso interactivo. Evidencias y capturas en `reports/ui-simplified/`, ignorado por Git.

Ejemplo verificado: 32.81517, -116.914566, radio 1000 m: **8 accidentes**; `A-44917` a 0 m. Se probaron radio/límite, cero resultados, entradas inválidas, cancelación, fallo de conexión/reintento, selección de tarjetas/marcadores y Vista de Estados Unidos.

Durante QA se corrigieron textos nuevos afectados por codificación y propagación del clic de marcadores al mapa. Se ajustaron las pruebas para coordenadas compartidas por distintos accidentes y para esperar la animación de cierre de Leaflet. La ejecución final no presenta fallos.

## Conservación del proyecto

MongoDB mantiene 1.103.657 accidentes e índice 2dsphere; analytics_grid 23.599, analytics_time 2.660, analytics_hotspots 50 y una ejecución/publicación analítica. Se verificaron fuente y hotspot principal contra la captura previa, sin cambios. No hubo descarga, ETL, Spark completo ni escrituras de datos.

Solo se recreó Flask con `parcialbigdata-api:ui-local`, revisión OCI `working-tree-ui` y límite original de 256 MiB. MongoDB, Jenkins, webhook y túnel conservaron sus contenedores. Se retiró exclusivamente la candidata temporal sin volúmenes. No se modificaron Compose ni Jenkinsfile; los checks de pytest y HTTP existentes incluyen la UI. Esta validación local no se presenta como un nuevo despliegue remoto desde GitHub.

Archivos de interfaz: `api/templates/dashboard.html`, `api/static/dashboard.js`, `api/static/dashboard.css`; pruebas `tests/test_dashboard.py` y `tests_ui/test_dashboard_browser.py`; documentación README y guía de uso. Las capacidades del backend se conservan. Los originales de la interfaz anterior se respaldaron bajo `reports/ui-simplified/original/`.

## Demostración

Abrir la URL, elegir un punto o escribir el ejemplo, ajustar radio, pulsar Buscar accidentes y seleccionar una tarjeta o marcador. Terminar con Vista de Estados Unidos. Comandos de inicio y pruebas en [interfaz-web.md](interfaz-web.md).

Limitaciones: las teselas requieren Internet; el respaldo local no muestra calles. Accidentes superpuestos pueden seleccionarse individualmente desde sus tarjetas. La cantidad presentada está limitada por la consulta y no representa todos los accidentes del dataset original. Un despliegue remoto del código anterior puede sustituir esta imagen hasta que se autorice publicar.
