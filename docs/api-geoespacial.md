# API geoespacial y resultados Spark

Base local: `http://127.0.0.1:5000`. Respuestas JSON. `/health` mantiene su contrato de liveness y no depende de MongoDB. El servicio no requiere ni ofrece ArcGIS, QGIS ni modelos de machine learning.

## Contrato HTTP

| Operación | Entrada | Resultado |
|---|---|---|
| `GET /accidents/near` | `lat`, `lon`, `radius_m`; `limit` opcional | Consulta MongoDB `$near`, ordenada por proximidad |
| `GET /accidents/geo-near` | Mismos parámetros | Pipeline cuyo primer paso es `$geoNear`; añade `distance_m` en metros |
| `POST /accidents/within` | JSON con `geometry` Polygon y `limit` opcional | Consulta `$geoWithin`, sin garantizar orden |
| `GET /analytics` | `kind`, `limit`, `offset` opcionales | Resultados Spark publicados: `grid`, `hotspots`, `hour`, `day` o `month`; por defecto `hotspots` |

Latitud entre -90 y 90; longitud entre -180 y 180; radio entre 1 y 50.000 metros. Todos deben ser finitos. `limit` entero entre 1 y 100, predeterminado 20. No se permiten parámetros desconocidos o repetidos ni documentos de consulta MongoDB suministrados por el cliente. Cada consulta tiene máximo de ejecución en MongoDB de 3.000 ms y obtiene a lo sumo `limit+1` documentos para calcular `has_more`.

El polígono debe ser un objeto GeoJSON con únicamente `type` y `coordinates`, un anillo exterior cerrado y entre 3 y 100 vértices distintos, más el vértice de cierre. Cada posición usa **[longitud, latitud]**, sin altitud. Se rechazan área cero, intersecciones y contactos del anillo consigo mismo, coordenadas inválidas y una caja que abarque más de 5° en cualquiera de sus ejes. Se admiten polígonos cóncavos; esta API no admite agujeros, cruce del antimeridiano, CRS personalizado, Feature ni MultiPolygon. MongoDB realiza además su validación esférica. El cuerpo está limitado a 32 KiB.

Las respuestas exitosas contienen `items`, `count` y `has_more`. `count` corresponde a los elementos devueltos, no al total de coincidencias. Las consultas de accidentes indican también `operator`; las de radio incluyen `radius_m`. Los documentos se proyectan a ID, Severity, Start_Time, City, State, location y dataset_fingerprint, más distance_m cuando corresponde. No se devuelve toda la descripción ni las 46 columnas.

`/analytics` añade `kind`, `offset` y `source` con run_id, source_fingerprint, source_rows, dataset_version, cell_degrees y time_basis. `offset` es un entero de 0 a 10.000; cada página conserva el límite máximo de 100. Grilla y hotspots se ordenan por conteo descendente; las series temporales, por bucket ascendente. Una página posterior usa offset anterior más limit, dentro del máximo permitido. La API lee exclusivamente el run_id señalado por `analytics_state`; nunca expone ejecuciones nuevas incompletas.

| HTTP | Significado |
|---|---|
| 200 | Consulta válida, incluso con items vacío |
| 400 | Parámetros o geometría inválidos; JSON malformado |
| 404 | Ruta inexistente |
| 405 | Método HTTP no admitido |
| 413 | Cuerpo demasiado grande |
| 415 | POST sin Content-Type application/json |
| 503 | MongoDB no disponible o resultados Spark aún no publicados |
| 504 | Consulta excedió el tiempo máximo |

Los errores tienen forma `{"error":{"code":400,"message":"..."}}`. No se devuelven credenciales ni mensajes internos del servidor MongoDB. El acceso HTTP está publicado únicamente en loopback; no se ha diseñado aún un servicio público autenticado.

## Ejemplos en Windows CMD

```cmd
cd /d D:\Proyects\ParcialBigData
curl.exe --fail "http://127.0.0.1:5000/accidents/near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail "http://127.0.0.1:5000/accidents/geo-near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail -H "Content-Type: application/json" --data-binary @examples\polygon.json http://127.0.0.1:5000/accidents/within
curl.exe --fail "http://127.0.0.1:5000/analytics?kind=hotspots&limit=3"
curl.exe --fail "http://127.0.0.1:5000/analytics?kind=month&limit=3"
curl.exe -i "http://127.0.0.1:5000/accidents/near?lat=91&lon=0&radius_m=1000"
```

La última llamada debe devolver 400. Los ejemplos de respuestas reales y las cantidades verificadas se registran en el informe de Fase 4.

## Modelo analítico

Spark lee la colección accidents mediante MongoDB Spark Connector, con esquema explícito y proyección de ID, coordenadas iniciales y Start_Time. Utiliza ocho particiones de lectura, un ejecutor con un core y 768 MiB, driver de 512 MiB y cuatro particiones shuffle. Persiste las columnas necesarias **en disco**, no recolecta el dataset en el driver y solo trae un registro agregado de métricas. La ventana de ranking se aplica al top 50 de celdas, no al millón de accidentes.

- `analytics_grid`: conteo por celda de 0,1°, índices floor((longitud+180)*10) y floor((latitud+90)*10), con máximos +180/+90 incluidos en la última celda. Cada fila contiene sus límites geográficos y conteo.
- `analytics_time`: conteo por hora del día (00–23), fecha civil y mes civil. Las fracciones de segundo no cambian esos grupos. Fechas que no se puedan analizar se contabilizan y se excluyen solo del agregado temporal; la grilla conserva el total.
- `analytics_hotspots`: las 50 celdas con mayor conteo, con desempate determinista por índices de celda y rank desde 1.
- `analytics_runs`: método, versión del dataset, hash CSV, huella de muestra, cantidades y verificación.
- `analytics_state`: puntero atómico a la última ejecución validada.

Son conteos de la muestra, sin extrapolación al dataset completo. Una celda angular no tiene la misma superficie en todas las latitudes; los hotspots indican concentración de registros, no riesgo vial ni tasa por población. Los tiempos son los civiles registrados por la fuente, asociados a distintas zonas; no se interpretan como instantes UTC comparables entre estados.

La identidad de resultados deriva de la huella de muestra, método y resolución. Las escrituras del conector son upserts por `_id` determinista. Cambiar la semántica del cálculo exige actualizar METHOD_VERSION para no reutilizar una caché obsoleta. Las versiones anteriores permanecen almacenadas; la API filtra por el puntero activo. No se sobrescribe accidents.

## Ejecutar y probar sin volver a ingerir

Requiere la ingesta completa de la Fase 3. Usar Python local exclusivamente desde `.venv`. PySpark y Java se ejecutan dentro de los contenedores existentes.

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pip install -r requirements\local.txt
python -m pytest tests -q
docker compose build spark-master api-tests
docker compose up -d --no-deps --no-build --wait spark-master spark-worker
python scripts\run_spark.py --test --label spark-tests-review
python scripts\run_spark.py --label spark-review
docker compose -f docker-compose.yml -f ci/compose.integration.yml run --rm --no-deps api-integration
```

Una ejecución analítica completa ya verificada se reutiliza por defecto. Solo para probar la repetición, añadir `--force` a run_spark.py. El mismo bloqueo de archivo impide solapar Spark con la ingesta Dask. No ejecutar otro spark-submit por fuera de estos puntos de entrada; el driver usa puertos fijos. Las pruebas escriben colecciones con prefijos aleatorios `phase4_*_test_` y eliminan únicamente esas colecciones.

run_spark.py conserva logs, resultado de ejecución y muestras de docker stats en `reports/phase4/`, excluido de Git. El informe de datos persiste en `/data/analytics-report.json`. Las mediciones son operativas; no son el benchmark formal Dask/Spark.

El pipeline local existente ahora exige pruebas Flask, infraestructura, pruebas Spark, resultados analíticos coherentes, integración API/MongoDB y smoke HTTP de una candidata antes de promover Flask. Reutiliza los resultados Spark existentes si son válidos. Mantiene recuperación del despliegue anterior ante fallo posterior. El checkout remoto y el webhook permanecen pendientes.

Fuentes técnicas: [lectura del conector](https://www.mongodb.com/docs/spark-connector/v10.x/batch-mode/batch-read-config/), [escritura del conector](https://www.mongodb.com/docs/spark-connector/v10.x/batch-mode/batch-write-config/), [funciones Spark 3.5.8](https://spark.apache.org/docs/3.5.8/sql-ref-functions-builtin.html), [consultas geoespaciales PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/geo/).
