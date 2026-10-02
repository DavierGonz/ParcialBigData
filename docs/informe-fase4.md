# Informe de Fase 4: Spark, consultas geoespaciales y Flask

Fecha de verificación: 27 de septiembre de 2026. Fase implementada y probada localmente; pendiente de revisión del equipo. No se avanzó al benchmark formal ni a la integración remota.

## Alcance y datos conservados

Se leyó íntegramente la guía original, los informes anteriores y el código. Se conservaron arquitectura, volúmenes, credenciales locales y datos. No hubo descarga Kaggle ni repetición del ETL Dask. `accidents` sigue conteniendo **1.103.657 documentos** y el índice `location_2dsphere`; no quedaron colecciones temporales de las pruebas. El documento de `Insumos` conserva SHA-256 `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`.

Trazabilidad de entrada:

- US Accidents, versión Kaggle **13**, muestra reproducible BLAKE2b con semilla `us-accidents-academic-v1` y módulo 7, generada en Fase 3.
- Huella de la ingesta: `cfce18489c4df70fe59c6166b61e0aafcebbb098b71b164ca9f9ada842fd22cf`.
- SHA-256 del CSV registrado en el manifiesto: `e3e9f962e3e2289db1bdce91623abbcf9ba4d7bfc1adb091c8aeee6c2639d204`. Esta fase reutiliza ese manifiesto; no volvió a calcular el hash de todo el CSV.
- Ejecución analítica: `05808ac04fd429936fb76b442b7389e96fd4fbe311512e0e0cf505e7c48b1631`; método `grid01-civil-time-v1`.

## Procesamiento y resultados

Spark **3.5.8**, MongoDB Spark Connector **10.7.0**, MongoDB **8.0.16**, PyMongo **4.15.1** y Flask **3.1.3**. Se conservan master y un worker Spark, scheduler y dos workers Dask, MongoDB, Flask y Jenkins. Las dependencias locales están en `.venv`; las de los contenedores se instalan en sus Dockerfiles.

El conector lee ocho particiones de MongoDB, filtradas por huella y proyectando solo ID, coordenadas y fecha. Spark calcula una grilla angular de **0,1° × 0,1°**, conteos por hora del día, fecha y mes, y las 50 celdas con más accidentes. Los datos intermedios se persisten con `DISK_ONLY`. El driver recibe contadores y resultados pequeños de verificación, nunca el dataset completo.

| Colección | Documentos finales | Verificación |
|---|---:|---|
| `analytics_grid` | 23.599 | Suma de conteos: 1.103.657 |
| `analytics_time` | 2.660 | 24 horas, 2.549 fechas y 87 meses |
| `analytics_hotspots` | 50 | Coinciden con las primeras 50 celdas de la grilla |
| `analytics_runs` | 1 | Versión, muestra, método, particiones, tiempos y resultados |
| `analytics_state` | 1 | Puntero a la ejecución completa publicada |

Cada granularidad temporal suma **1.103.657**. Fechas no interpretables en la muestra real: **0**. Las horas conservan el tiempo civil del archivo, sin conversión a UTC; no permiten inferir simultaneidad entre estados con husos diferentes. La celda principal contiene **7.176 accidentes**, longitud −118,3 a −118,2 y latitud 34,0 a 34,1. Son frecuencias de la muestra, no tasas de riesgo; las celdas angulares no tienen la misma superficie a distintas latitudes.

Los identificadores incluyen la ejecución y la clave de agrupación. Las escrituras usan reemplazo con upsert por lotes de 250. Una segunda escritura no duplica resultados. Cambiar la semántica del algoritmo requiere incrementar su versión. Se verifica la consistencia antes de publicar el puntero activo; los resultados incompletos no se ofrecen por la API. Las ejecuciones completas de la misma muestra se reutilizan después de verificar sus totales. El bloqueo del volumen compartido impide solapar el procesamiento con una ingesta Dask pesada.

## API desplegada

Contrato completo, campos y restricciones: [api-geoespacial.md](api-geoespacial.md).

| Operación | Entrada | Consulta / salida |
|---|---|---|
| `GET /health` | Ninguna | Estado del proceso Flask |
| `GET /accidents/near` | `lat`, `lon`, `radius_m`, `limit` opcional | `$near`, registros cercanos |
| `GET /accidents/geo-near` | Mismos parámetros | Agregación con `$geoNear` primero, distancias en metros |
| `POST /accidents/within` | JSON `geometry` Polygon y `limit` opcional | `$geoWithin`, puntos interiores |
| `GET /analytics` | `kind`, `limit`, `offset` opcionales | Grilla, hotspots, hora, día o mes de ejecución publicada |

Coordenadas finitas y dentro de rango; radio de 1 a 50.000 m; máximo 100 resultados, 20 por defecto; offset analítico máximo 10.000. Polygon admite un anillo exterior cerrado, sin huecos ni autointersecciones, entre 3 y 100 vértices distintos, dos coordenadas por posición y extensión máxima de 5° por eje. No se admiten antimeridiano, Feature, MultiPolygon ni CRS. Cuerpo máximo 32 KiB. Cada consulta MongoDB tiene límite de 3 segundos y lee como máximo `limit + 1` documentos para informar `has_more`.

HTTP: 200 correcto; 400 entrada inválida; 404 ruta inexistente; 405 método incorrecto; 413 cuerpo excesivo; 415 contenido incompatible; 503 base no disponible o agregados aún no publicados; 504 consulta agotada. Los errores no exponen credenciales ni detalles internos de MongoDB.

Ejemplos **reales**, capturados desde la API desplegada después del build #8, todos HTTP 200:

- Cerca de `lat=32.81517&lon=-116.914566&radius_m=1000&limit=2`: `count=2`, `has_more=true`, IDs `A-44917` y `A-71824`, ambos El Cajon, CA.
- La misma entrada en `/accidents/geo-near` devuelve distancias **0,0 m** y **447,7373151480544 m**, respectivamente, y `operator="$geoNear"`.
- `POST /accidents/within` con `examples/polygon.json`: `count=2`, `has_more=true`, IDs observados `A-495916` y `A-344456`; este operador no garantiza orden de proximidad.
- `/analytics?kind=hotspots&limit=1`: celda `(617,1240)`, `rank=1`, `count=7176`, `min_lon=-118.3`, `max_lon=-118.2`, `min_lat=34.0`, `max_lat=34.099999999999994`. El último decimal es representación de punto flotante.

Las respuestas JSON completas, incluida la procedencia analítica, están en `reports/phase4/final-verification.json` (evidencia local excluida de Git).

## Pruebas y tiempos reales

| Ejecución | Resultado | Tiempo observado |
|---|---|---:|
| Unitarias locales finales | 46 aprobadas | 0,38 s |
| Fixture Spark/MongoDB manual | 1 aprobada, escrituras repetidas sin duplicados | 17,66 s de pytest; 28,094 s del comando |
| Integración API/MongoDB manual final | 4 aprobadas | 0,73 s |
| Spark completo, tras corregir permisos | Correcto, 1.103.657 entradas | 120,162 s del job; 128,016 s del comando |
| Reutilización manual | Correcta, sin reprocesar los datos | 2,686 s del job; 7,563 s del comando |
| Jenkins #7, fallo intencional | 46 aprobadas + 1 fallo deliberado; no desplegó | 31,489 s del build |
| Jenkins #8, normal | SUCCESS, 51 pruebas aprobadas | 97,308 s del build |

En #8: 46 unitarias (JUnit 0,311 s), una prueba Spark con varias comprobaciones (16,374 s), cuatro de API/MongoDB (0,639 s); cero fallos, errores u omisiones. El job analítico reutilizó resultados y verificó totales en 1,873 s. Además pasaron conectividad de infraestructura, candidata, endpoints por HTTP y comprobación de la API desplegada. El tiempo total CI incluye construcción y operaciones Docker; no equivale al tiempo de procesamiento completo.

La prueba Spark usa cinco documentos conocidos, incluidos extremos de coordenadas, una fecha inválida y una con fracciones de segundo; verifica claves y conteos espaciales/temporales y escribe dos veces las tres colecciones. Las pruebas geoespaciales usan puntos conocidos para comprobar proximidad, distancia, inclusión, límites, publicación y datos reales. Cada fixture limpia únicamente sus colecciones con UUID.

Jenkins #7 terminó antes de desplegar; `verify 7` confirmó que contenedor e imagen de Flask permanecieron iguales. Jenkins #8 desplegó la revisión `89d65d7`; `verify 8` comprobó resultado y revisión. El pipeline exige marcas satisfactorias de unitarias, infraestructura, Spark/analítica, integración API y candidata antes de promover la imagen. Los logs y XML se conservan en `reports/jenkins/build-7/` y `build-8/`, además de los artefactos en Jenkins. El checkout remoto y webhook permanecen pendientes.

## Fallos encontrados y resolución

1. Docker Desktop estaba detenido al comenzar; se inició y recuperó los servicios. No se restableció a valores de fábrica ni se eliminaron volúmenes.
2. Primer ensayo Spark: error de sintaxis por paréntesis faltante en una expresión. Se corrigió antes de las pruebas satisfactorias y del commit.
3. Primera ejecución sobre la muestra: completó las escrituras pero falló al guardar `/data/analytics-report.tmp` por permisos (107,032 s del comando). Spark usaba grupo primario 185, mientras el volumen compartido permite escritura al grupo 0. Se fijó `USER 185:0`, conservando usuario no root. El informe se escribe ahora antes de publicar la ejecución; una repetición completa terminó correctamente sin duplicados.
4. Una integración se lanzó mientras aún no estaban publicados los agregados: tres pruebas pasaron y una recibió el 503 previsto por esa protección. Tras publicar, las cuatro pasaron; Jenkins ahora secuencia explícitamente Spark antes de la integración API.
5. El fallo pytest del build #7 fue provocado para verificar la barrera de despliegue y se conserva como evidencia. No es un fallo pendiente del producto.

## Recursos observados

Sin aumentar los límites existentes, sin ETL Dask pesado simultáneo. Medición con `docker stats`, 26 muestras durante el procesamiento completo, aproximadamente una cada cinco segundos; registros en `reports/phase4/spark-complete-resources.jsonl` y resumen en `resource-summary.json`.

| Contenedor | Máximo observado | Límite |
|---|---:|---:|
| Spark master / driver | 498,3 MiB | 1.024 MiB |
| Spark worker | 787,0 MiB | 1.536 MiB |
| MongoDB | 726,0 MiB | 768 MiB |
| Jenkins | 396,0 MiB | 1.024 MiB |
| Flask | 53,55 MiB | 256 MiB |
| Dask scheduler | 147,8 MiB | 384 MiB |
| Dask worker 1 / 2 | 169,6 / 117,3 MiB | 1.024 MiB cada uno |

El máximo de la suma simultánea de los ocho servicios fue **2.770,23 MiB (~2,705 GiB)**. Los máximos individuales no necesariamente coinciden. No incluye toda la VM, BuildKit ni aplicaciones Windows y no garantiza captar picos entre muestras. MongoDB registró presión en su límite (`memory.events max=55977`), pero `oom=0` y `oom_kill=0` durante las verificaciones manuales. Al cierre los ocho contenedores están **running/healthy**, todos con `OOMKilled=false`. La memoria libre de Windows llegó a 802.304 KiB en una lectura previa al procesamiento; no se midió un máximo continuo del host. Mantener ejecuciones pesadas secuenciales.

Estas mediciones son de operación y verificación de esta fase; no constituyen el benchmark comparativo Dask/Spark.

## Archivos y Git

Implementación en `processing/`, `api/repository.py`, `api/validation.py`, factoría Flask, `tests/test_geo.py`, `tests_processing/`, `tests_api_integration/`, `scripts/run_spark.py`, `scripts/smoke_geo.py` y `examples/polygon.json`. Se actualizaron Dockerfiles de API, Spark e ingesta, dependencias MongoDB/Spark/API, Jenkinsfile, `ci/pipeline.sh`, redes de candidata y Compose de integración. La guía `docs/api-geoespacial.md` acompaña el código. El commit contiene 28 archivos; los documentos de cierre actualizan README, arquitectura, requisitos y política Git.

Rama: **develop/final-delivery**. Se creó **un solo commit adicional**, `89d65d79b51264bc303481ec2f1aba12e88057d7`, imprescindible para que el mecanismo existente de Jenkins exportara y probara una revisión exacta mediante bundle local. No hubo commits por archivo ni por corrección. Este informe y las actualizaciones de cierre permanecen localmente sin commit. No hubo push ni PR. `main` y la referencia local `origin/main` siguen en `2ec352a90f7cd37488bf040f6da13a2435a82350`; no se modificó el remoto ni se reescribió historial. La consolidación de commits no publicados se evaluará antes de la entrega final, conservando evidencias.

Se revisaron los archivos antes del commit con el control de rutas/secretos y se auditó después el contenido de trabajo de 82 archivos, incluido este informe, sin detectar secretos ni rutas prohibidas. `.env`, `.venv`, credenciales, datasets, `Insumos` y `reports` permanecen fuera del control de versiones. Las pruebas no atribuyen aportes ficticios a estudiantes.

## Verificación en Windows CMD

Con Docker iniciado y los servicios existentes levantados:

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
docker compose ps
python -m pytest tests -q
curl.exe --fail http://127.0.0.1:5000/health
curl.exe --fail "http://127.0.0.1:5000/accidents/near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail "http://127.0.0.1:5000/accidents/geo-near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail -H "Content-Type: application/json" --data-binary @examples\polygon.json http://127.0.0.1:5000/accidents/within
curl.exe --fail "http://127.0.0.1:5000/analytics?kind=hotspots&limit=3"
python scripts\smoke_geo.py http://127.0.0.1:5000
python scripts\run_spark.py --label spark-review
python scripts\jenkins_local.py status 8
python scripts\jenkins_local.py verify 8
```

Pruebas de integración, de forma secuencial y sin otro trabajo Spark o Dask pesado:

```cmd
python scripts\run_spark.py --test --label spark-review-tests
docker compose build api-tests
docker compose -f docker-compose.yml -f ci/compose.integration.yml run --rm --no-deps api-integration
docker stats --no-stream
```

`run_spark.py` normal reutiliza el resultado completo; `--force` recalcula únicamente Spark si se necesita una nueva medición. No es necesario para revisar los resultados. Los documentos locales sin commit no afectan estos comandos ni la consulta de builds existentes; preparar un nuevo bundle con el helper sí exige árbol limpio, según su contrato. No crear otro commit solo para guardar este cierre.

Para detener y reanudar conservando los datos:

```cmd
docker compose stop
docker compose start --wait
```

Pendientes deliberados: aprobación de Fase 4, benchmark formal, checkout remoto/webhook y validación de entrega final, informe académico final y ensayo en otro equipo. No quedan fallos conocidos bloqueantes de esta fase. Se detiene el desarrollo hasta la revisión y aprobación del equipo.
