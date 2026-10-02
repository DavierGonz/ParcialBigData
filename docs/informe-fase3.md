# Informe de Fase 3: Kaggle, Dask y MongoDB

Ejecuciones reales del 27 de septiembre de 2026 en Windows, Docker Desktop y Jenkins local. Esta fase comprende descarga, limpieza, muestreo y carga. No implementa agregaciones Spark, endpoints geoespaciales de negocio, checkout remoto ni webhook.

## Dataset, esquema y cantidades verificadas

La API de Kaggle descargó íntegramente `sobhanmoosavi/us-accidents`, **versión 13**, actualizada en origen el 28 de mayo de 2023. La credencial se registró como Secret text de Jenkins con ID `parcialbigdata-kaggle`, sin incluir su valor en Git, imágenes o informes. El primer job hizo la descarga, extracción y carga sin intervención manual.

| Medida | Resultado real |
|---|---:|
| ZIP descargado | 684.855.912 bytes |
| CSV completo | 3.058.183.727 bytes |
| Columnas del CSV | 46 |
| Registros leídos por Dask | 7.728.394 |
| Descartados por coordenadas ausentes | 0 |
| Descartados por coordenadas no numéricas/no finitas | 0 |
| Descartados por coordenadas fuera de rango | 0 |
| Descartados por ID ausente | 0 |
| Registros limpios | 7.728.394 |
| Limpios no incluidos por el muestreo | 6.624.737 |
| Documentos seleccionados y almacenados | **1.103.657** |
| Filas seleccionadas duplicadas por ID | 0 |
| Particiones CSV ejecutadas | 182 |

Los cero descartes corresponden a `Start_Lat`/`Start_Lng` en este archivo real; no significan que todas las demás columnas estén completas. Las pruebas sí ejercitan coordenadas vacías, nulas, texto, infinito y valores fuera de rango. Los registros no seleccionados para la muestra se contabilizan por separado y no se presentan como errores de limpieza.

Archivo: `US_Accidents_March23.csv`. SHA-256: `e3e9f962e3e2289db1bdce91623abbcf9ba4d7bfc1adb091c8aeee6c2639d204`.
ZIP SHA-256: `849be2b58b796fe4fa3b8857446b967fe96aacb9e7f0d6b709ee18cc9693b3c4`.
Huella de CSV, versión, ETL y muestra: `cfce18489c4df70fe59c6166b61e0aafcebbb098b71b164ca9f9ada842fd22cf`.

Se inspeccionó el esquema del CSV descargado. Incluye ID, Source, Severity, tiempos inicial/final, coordenadas iniciales/finales, Distance(mi), Description, ubicación administrativa, Timezone, variables meteorológicas, indicadores viales y crepúsculos. La lista completa de 46 columnas se conserva en el manifiesto y en los informes de las ejecuciones completas. Los tiempos civiles originales se conservan con Timezone; no se convierten arbitrariamente a UTC.

## Arquitectura y decisiones

Se mantienen los ocho servicios persistentes y sus límites. Un contenedor efímero `ingestion` (512 MiB, 1 CPU) accede a Kaggle por la red `ci` y a Dask/MongoDB por `backend`. Comparte el volumen existente `dataset_cache` con los workers. El nuevo job [parcialbigdata-ingestion-local](http://127.0.0.1:8080/job/parcialbigdata-ingestion-local/) utiliza Git bundles locales y un Jenkinsfile propio; no modifica el despliegue de Flask.

La caché guarda ZIP, CSV y manifiesto con versión, licencia, fecha, tamaños, esquema y SHA-256. Se comprueba longitud HTTP e integridad ZIP, se rechazan rutas de extracción inseguras y se publica el manifiesto al finalizar. Un bloqueo sobre el volumen evita ingestas concurrentes. La reutilización verifica hashes sin descargar; una ingesta ya completa verifica también MongoDB y omite el ETL.

El coordinador mantiene como máximo dos particiones en vuelo, con bloques CSV de 16 MiB y límite de proceso Dask de 768 MiB por worker. Recibe contadores, no el dataset completo. Las tareas reales se ejecutaron en **worker-1 y worker-2**. La muestra usa BLAKE2b de 64 bits, semilla `us-accidents-academic-v1` e inclusión por módulo 7 igual a cero; no depende del orden de ejecución.

Los puntos son `location: {type: "Point", coordinates: [longitud, latitud]}`. La escritura usa lotes de 500, `_id=ID` y ReplaceOne/upsert. La colección `ingestion_runs` registra finalización únicamente después de verificar el mínimo de un millón, geometrías e índice. Una ejecución interrumpida puede dejar documentos parciales; la repetición los recupera sin duplicarlos. No se implementó intercambio atómico entre versiones ni borrado de datos anteriores.

Se conservan Dask/distributed 2025.5.1, pandas 2.3.3, PyArrow 25.0.1, PyMongo 4.15.1, Python de contenedores 3.10.20, MongoDB 8.0.16 y Jenkins 2.568.3. La API REST de Kaggle se consume con la biblioteca estándar Python; no se añade un SDK flotante. `requirements/local.txt` reúne las dependencias locales dentro de `.venv`; los contenedores instalan sus propias dependencias.

## Pruebas y tiempos

Todas las duraciones siguientes son mediciones reales; no constituyen el benchmark Dask/Spark de una fase posterior. La columna obtención/caché incluye descarga, extracción y hashes en el primer build; en los siguientes corresponde a verificar la caché local. El tiempo total de datos incluye verificación MongoDB. Jenkins incluye además construcción, pruebas y preparación.

| Build | Escenario | Obtención/caché | ETL | Total de datos | Jenkins |
|---|---|---:|---:|---:|---:|
| #1 | Primera descarga y carga | 74,315 s | 106,216 s | 186,659 s | 261,421 s |
| #2 | Repetición forzada | 3,126 s | 94,982 s | 104,057 s | 136,836 s |
| #3 | Reutilización de caché y ETL completo | 2,864 s | Omitido | 8,802 s | 42,186 s |
| #4 | Repetición tras corregir orden BSON | 2,649 s | 85,598 s | 95,640 s | 130,243 s |

Los cuatro builds finalizaron SUCCESS y conservaron exactamente 1.103.657 documentos. #2, #3 y #4 descargaron **0 bytes**. #2 insertó cero documentos y encontró 1.103.657 existentes. Se detectaron reemplazos redundantes por el orden BSON de `_id`; se ajustó la serialización para que `_id` vaya primero y se añadió una prueba que exige cero modificaciones al repetir. **#4 verificó 0 insertados, 1.103.657 encontrados y 0 modificados**, con la misma muestra y huella. Su código corresponde al commit `55c950a`; los cambios posteriores de cierre son documentales.

Pruebas locales finales: **17 passed, 2 skipped en 1,57 s**. Las dos omitidas requieren Linux y servicios Docker. Pruebas Docker: **15 passed** sin omisiones. Jenkins ejecuta 14 pruebas aprobadas y una integración omitida deliberadamente en la etapa unitaria; después ejecuta las tres pruebas de integración, sin omisiones. Estas incluyen descarga HTTP de fixture ZIP, bloqueo concurrente y lectura CSV distribuida con escritura real en una colección MongoDB temporal aislada. Esta última verifica ambos workers, upserts, repetición y rechazo de geometría inválida; elimina únicamente su propia colección de prueba.

MongoDB verificó el índice `location_2dsphere` (versión 3), el formato y rango de **todos** los puntos de la huella. Una consulta `$near` devolvió cinco documentos y `$geoWithin` encontró ocho en un radio de 1 km alrededor del punto de control `[-116.914566, 32.81517]`. Son pruebas de almacenamiento; no se añadieron endpoints de negocio.

## Recursos y problemas encontrados

Se capturaron **60 muestras** entre los cuatro builds (28, 16, 2 y 14). El mayor consumo agregado observado de los nueve contenedores fue **3.128,06 MiB (3,055 GiB)** durante #2; en la ejecución final #4 fue 2.787,74 MiB (2,722 GiB). Máximos individuales entre todas las muestras: worker-1 494,7 MiB, worker-2 507,2 MiB, coordinador 357,5 MiB, scheduler 144,5 MiB, MongoDB 722,7 MiB y Jenkins 658,7 MiB. Esos máximos individuales no ocurrieron necesariamente juntos; las muestras no garantizan capturar cada pico.

Los límites permanentes suman 6,875 GiB; el coordinador añade un límite de 512 MiB, sin reservar toda esa memoria. Docker tiene aproximadamente 7,64 GiB. Windows mostró poco margen libre, entre aproximadamente 330 y 508 MiB en varias lecturas durante la carga. Ese dato incluye la presión de otras aplicaciones y WSL, no solo los procesos del proyecto. MongoDB estuvo cerca de su límite de 768 MiB y registró reclamación de memoria al alcanzar el límite, pero sus contadores OOM y OOM kill permanecieron en cero. No se incrementó la memoria global de Docker ni se ejecutaron cargas Spark simultáneas.

Incidencias resueltas:

- Docker Desktop no arrancaba por sockets temporales de `dockerInference` y `docker-secrets-engine/engine.sock`. Se conservaron los directorios temporales como copias y Docker los regeneró; no se restableció de fábrica ni se borraron volúmenes.
- La primera prueba distribuida no encontraba el módulo ingestion desde el proceso Dask. Se fijó `PYTHONPATH=/app` en la imagen común y se repitió satisfactoriamente la integración.
- Se identificó y corrigió el orden BSON que causaba reemplazos de documentos lógicamente idénticos.

## Archivos y control de versiones

```text
ingestion/                     descarga, transformación, carga y coordinación
tests_ingestion/               pruebas unitarias, HTTP y Dask/MongoDB reales
docker/ingestion/Dockerfile    coordinador y contenedor de pruebas
docker/dask/Dockerfile         módulo ETL y ruta de importación compartida
ci/compose.ingestion.yml       servicios efímeros y presupuesto de memoria
ci/Jenkinsfile.ingestion       etapas y credencial segura
ci/ingestion.sh                barreras, ejecución, métricas y comprobación de Flask
scripts/jenkins_ingestion.py   credencial, job, bundles y verificación de artefactos
requirements/local.txt        dependencias locales reproducibles
docs/ingesta.md                operación CMD y reglas completas
```

También se actualizaron `scripts/jenkins_local.py` para seleccionar el Jenkinsfile, `scripts/check_staged.py` para detectar los secretos locales de Kaggle/Jenkins antes de cada commit, `.env.example`, README y documentación de arquitectura/requisitos. `Insumos` mantiene el SHA-256 original `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`.

Se revisaron 83 versiones únicas de archivos en los nueve commits locales anteriores al cierre, sin encontrar valores de los secretos conocidos de MongoDB, Jenkins o Kaggle. El hook volvió a revisar el contenido preparado antes del commit documental. No quedaron archivos `.env.ci` en el workspace del job. La verificación final independiente, sin credencial Kaggle, confirmó de nuevo 1.103.657 geometrías válidas y reutilizó la caché en 9,775 s; los ocho contenedores estaban saludables y con `OOMKilled=false`.

Rama: **develop/final-delivery**, local sin upstream. Commits de esta fase: `0ac8948` (ETL/caché/pruebas), `ddfc539` (Jenkins y credencial), `1a9225a` (operación y salud HTTP), `cd90fe6` (trazabilidad), `55c950a` (upserts sin reemplazos innecesarios), más el commit documental de cierre. No hubo push ni nuevos pull requests. La consulta remota confirmó `main=2ec352a` y `feat/phase-1-infrastructure=8489629`, sin rama remota de desarrollo.

## Comandos de revisión en Windows CMD

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pytest tests tests_ingestion -q
docker compose ps
curl.exe --fail http://127.0.0.1:5000/health
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion python -m ingestion.run --verify-only
python scripts\jenkins_ingestion.py status 1
python scripts\jenkins_ingestion.py status 2
python scripts\jenkins_ingestion.py status 3
python scripts\jenkins_ingestion.py status 4
git status --short --branch
git log --oneline main..HEAD
```

Para una ejecución normal: `python scripts\jenkins_ingestion.py run`. Para forzar la prueba de repetición: añadir `--force-etl`. La guía [ingesta.md](ingesta.md) documenta preparación desde cero, credenciales y pruebas Docker. Jenkins conserva XML y JSON de evidencia; las copias locales están en `reports/ingestion-jenkins/`, excluido de Git. No se avanza a la fase siguiente sin revisión y aprobación del equipo.

Estado de cierre: ocho servicios saludables, Flask con HTTP 200 y el mismo contenedor e imagen, sin contenedores temporales de ingesta activos. Permanecen pendientes exclusivamente las fases posteriores y la integración remota final; no hay un bloqueo técnico abierto para esta ingesta. El margen de memoria de Windows y la cercanía de MongoDB a su límite deben considerarse al diseñar la próxima carga Spark.
