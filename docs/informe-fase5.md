# Fase 5 — Benchmark formal Dask vs Spark

Fecha: **1 de octubre de 2026**, America/Bogota. Los timestamps brutos usan UTC (2 de octubre durante esta sesión). Alcance exclusivo: agregación espacial por grilla sobre la muestra existente. No se descargó Kaggle, no se repitió el ETL y no se modificaron las colecciones productivas ni los endpoints.

## Metodología y equivalencia

Se releyó la guía original y se revisaron los informes y código anteriores. La operación es contar accidentes por celda angular de **0,1° × 0,1°**, sobre exactamente **1.103.657 accidentes** de US Accidents v13. Reglas idénticas:

```text
cell_x = min(3599, floor((longitud + 180) * 10))
cell_y = min(1799, floor((latitud + 90) * 10))
agrupar por (cell_x, cell_y) y contar
```

Los extremos +180/+90 pertenecen a la última celda. No se cambia a división por 0,1 ni se redondean previamente las coordenadas: eso podría alterar resultados en fronteras por representación binaria. La muestra ya está limpia; el preparador verifica nuevamente coordenadas finitas y dentro de rango, sin descartar ni remuestrear documentos.

Spark reutiliza **sin cambios** `processing.aggregates.prepare` y `aggregate`, seleccionando únicamente la grilla; no calcula ni escribe los agregados temporales o hotspots. Dask implementa la misma fórmula vectorizada con DataFrame, agrupación distribuida y cuatro particiones de salida. Spark usa cuatro particiones shuffle y desactiva AQE para conservar esa configuración. Ambos leen ocho particiones de entrada.

### Entrada común y alcance de los tiempos

Para aislar la comparación de los lectores diferentes de MongoDB, se exportó **una sola proyección persistente** de la muestra: ID, longitud, latitud y fecha original. Se recorrió MongoDB en orden de `_id`, por lotes de 1.000, distribuyendo los documentos entre ocho CSV. No se volvió a ejecutar la limpieza Dask ni se descargó el archivo de Kaggle. La copia está en el volumen existente, `/data/benchmark-v1/`; no se versionan los accidentes.

Ambos motores leen los mismos bytes, con tipos explícitos para coordenadas; Dask usa conversión de coma flotante `round_trip`. Cada CSV constituye una partición: `blocksize=None` en Dask y `spark.sql.files.minPartitionNum=1` con unión de ocho lecturas explícitas en Spark. El programa exige que ambos tengan ocho particiones. La proyección completa ocupa **60.774.261 bytes**, aproximadamente 58 MiB; es mucho menor que el CSV original de 46 columnas. Por eso las conclusiones solo cubren esta operación y proyección, no la ingesta completa ni cargas de mayor volumen.

La preparación, excluida del tiempo de los motores, duró **7,207 s**. El manifiesto conserva conteos, tamaños y SHA-256 de cada CSV, versión, huella de muestra y hash de IDs ordenados. En siguientes invocaciones se verifican estos hashes y se reutiliza la copia. La comprobación de archivos lee sus bytes y puede calentar la caché del sistema operativo; no se presenta ninguna ejecución como lectura de disco en frío.

- Huella de muestra: `cfce18489c4df70fe59c6166b61e0aafcebbb098b71b164ca9f9ada842fd22cf`.
- SHA-256 de IDs ordenados: `91ca1b4849c4fdec647dca6f92bcf00df46b40ff39136b675de6dbada390f47a`.
- SHA-256 de la grilla canónica: `a246a5516a5b27ff6e15d4766e1e9515eff8d4b52db9fc248d2e6871a398b60b`.

El preparador calcula además una referencia escalar durante la lectura y la compara con las **23.599 celdas** ya publicadas por Spark en Fase 4. Cada ejecución Dask/Spark compara exactamente todas las tuplas ordenadas `(cell_x, cell_y, count)` con esa referencia. No basta con coincidir en número de celdas o suma. Solo se recogen esas celdas agregadas en el driver; nunca el millón de filas de entrada. La suma esperada es **1.103.657** en todas las repeticiones.

## Configuraciones y control de recursos

Docker Engine 29.5.3, memoria visible **8.205.778.944 bytes (~7,64 GiB)** y 16 CPU lógicas visibles; host Windows con 16 GB de RAM. Motores Dask/distributed 2025.5.1 y Spark 3.5.8, imágenes ya fijadas en el proyecto. Los IDs de imágenes y hashes del código realmente usado se conservan en `benchmark/environment.json`.

| Configuración | Workers por motor | CPU por worker | Límite contenedor por worker | Memoria de proceso Dask / heap ejecutor Spark | Coordinador y driver |
|---|---:|---:|---:|---:|---|
| C1 | 1 | 1 | 1.536 MiB | 768 MiB | 1 CPU, 1.024 MiB |
| C2 | 2 | 1 cada uno | 1.536 MiB cada uno | 768 MiB cada uno | 1 CPU, 1.024 MiB |

Cada worker usa un hilo/core. Spark mantiene driver de 512 MiB de heap dentro del coordinador. El límite Dask se aplica al proceso y el de Spark al heap JVM: no son conceptos idénticos, aunque las cuotas exteriores de CPU y memoria sí son iguales. Se mide el consumo total del motor, incluido su coordinador, para no ocultar esa diferencia.

Se crearon servicios temporales en el proyecto **pbd-benchmark**, sin puertos publicados, con una red interna. Antes de medir se detuvieron los cinco servicios habituales de cómputo. MongoDB, Flask y Jenkins continuaron activos, sin ejecutar jobs concurrentes. C1 tiene un presupuesto de contenedores activos de **4,5 GiB**, y C2 de **6 GiB**, contando MongoDB (768 MiB), Flask (256 MiB) y Jenkins (1.024 MiB). No se aumentó el límite global Docker ni los límites de servicios productivos.

El worker Dask temporal tiene 1.536 MiB en vez de los 1.024 MiB del worker productivo para igualar la cuota exterior de Spark; su memoria de proceso sigue en 768 MiB. Esa asignación se compensa deteniendo el otro clúster y reduciendo el presupuesto concurrente respecto de los 6,875 GiB de servicios permanentes. No representa una necesidad de memoria demostrada para Dask ni un cambio permanente de arquitectura.

El orden de bloques fue Dask C1 → Spark C1 → Spark C2 → Dask C2. En cada bloque: **un calentamiento excluido de las estadísticas y tres ejecuciones medidas**. Los clústeres permanecen encendidos dentro del bloque, pero cada repetición crea una aplicación Spark/cliente Dask nueva. No se persisten los DataFrames ni se reutilizan agregados. El calentamiento beneficia cachés de archivos y procesos permanentes; no conserva una JVM de aplicación Spark entre repeticiones. No se estudió el caso de varias operaciones dentro de una sesión Spark duradera.

La ejecución es secuencial, con bloqueo compartido con el ETL. El arnés restaura los servicios habituales en `finally` incluso si una medición falla. No deben ejecutarse jobs Jenkins durante el benchmark: crear contenedores, desplegar o lanzar otros drivers alteraría las condiciones medidas.

## Qué significa cada métrica

- **Total s:** reloj monotónico desde lanzar `docker compose exec` hasta su salida. Incluye arranque de Python/spark-submit y cliente/sesión, lectura, planificación, agregación, recogida de celdas, comprobaciones y cierre. Excluye preparación de la copia, creación del clúster, captura de contadores y copia de evidencias al host.
- **Operación s:** desde construir la lectura hasta materializar las celdas en el driver. Incluye lectura CSV, planificación, comunicación y agregación; no pretende medir exclusivamente el kernel de agrupación. Excluye comprobación de igualdad y cierre de la sesión.
- **Pico motor MiB:** máximo observado de la suma simultánea del coordinador y workers activos, según `docker stats`. No es la suma de máximos individuales. Se conservan también las lecturas de MongoDB, Flask y Jenkins y los máximos individuales de los workers.
- **Memoria:** muestras aproximadamente cada segundo; pueden perder picos breves. La CLI Docker muestra consumo de contenedor ajustado por caché, no solo heap/RSS del algoritmo. No incluye toda la VM, Windows u otras aplicaciones.
- **CPU s:** diferencia acumulada de `cpu.stat usage_usec` de los contenedores del motor. Incluye sus procesos auxiliares. **CPU cores media** es CPU s / ventana de contadores; 1 equivale aproximadamente a un core ocupado. Esa ventana rodea la ejecución y es algo mayor que `Total s`, por la lectura secuencial de contadores. Sus límites y contadores brutos quedan registrados.
- **Errores/reintentos:** salida del proceso, eventos de tareas fallidas y nuevos intentos Spark, claves de tareas repetidas en el task stream Dask; reintentos solicitados por aplicación desactivados. OOM se comprueba por diferencia de `memory.events oom_kill`. Se informa también cuántos workers realmente ejecutaron tareas.

## Resultados

| Motor | Workers | n | Total mediana s | Min–max s | Operación mediana s | Pico motor MiB | CPU s mediana | CPU cores mediana | Errores / reintentos / OOM |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| dask | 1 | 3 | 3.022 | 3.021–3.041 | 1.752 | 424.9 | 3.074 | 0.830 | 0 / 0 / 0 |
| dask | 2 | 3 | 2.384 | 2.264–2.388 | 1.034 | 575.7 | 3.458 | 1.042 | 0 / 0 / 0 |
| spark | 1 | 3 | 16.344 | 15.825–17.870 | 11.409 | 919.1 | 19.962 | 1.192 | 0 / 0 / 0 |
| spark | 2 | 3 | 15.153 | 15.043–16.114 | 10.065 | 1306.5 | 26.219 | 1.664 | 0 / 0 / 0 |

## Ejecuciones individuales (calentamientos separados)

| Motor | Workers | Tipo / iteración | Total s | Operación s | Pico MiB | CPU s | Frames memoria | Registros / celdas / suma |
|---|---:|---|---:|---:|---:|---:|---:|---|
| dask | 1 | calentamiento | 3.714 | 2.404 | 383.5 | 3.714 | 5 | 1103657 / 23599 / 1103657 |
| dask | 1 | 1 | 3.022 | 1.748 | 424.7 | 3.086 | 3 | 1103657 / 23599 / 1103657 |
| dask | 1 | 2 | 3.021 | 1.752 | 424.9 | 3.053 | 3 | 1103657 / 23599 / 1103657 |
| dask | 1 | 3 | 3.041 | 1.776 | 411.2 | 3.074 | 3 | 1103657 / 23599 / 1103657 |
| spark | 1 | calentamiento | 16.318 | 10.961 | 901.2 | 19.553 | 17 | 1103657 / 23599 / 1103657 |
| spark | 1 | 1 | 16.344 | 11.409 | 915.0 | 19.962 | 17 | 1103657 / 23599 / 1103657 |
| spark | 1 | 2 | 15.825 | 11.197 | 908.8 | 19.883 | 17 | 1103657 / 23599 / 1103657 |
| spark | 1 | 3 | 17.870 | 12.025 | 919.1 | 21.298 | 19 | 1103657 / 23599 / 1103657 |
| spark | 2 | calentamiento | 16.882 | 11.115 | 1282.4 | 28.599 | 18 | 1103657 / 23599 / 1103657 |
| spark | 2 | 1 | 16.114 | 10.664 | 1296.8 | 27.405 | 16 | 1103657 / 23599 / 1103657 |
| spark | 2 | 2 | 15.043 | 10.065 | 1306.5 | 26.022 | 16 | 1103657 / 23599 / 1103657 |
| spark | 2 | 3 | 15.153 | 10.028 | 1295.1 | 26.219 | 16 | 1103657 / 23599 / 1103657 |
| dask | 2 | calentamiento | 3.058 | 1.768 | 518.2 | 4.588 | 4 | 1103657 / 23599 / 1103657 |
| dask | 2 | 1 | 2.388 | 1.050 | 523.0 | 3.475 | 3 | 1103657 / 23599 / 1103657 |
| dask | 2 | 2 | 2.384 | 1.032 | 547.1 | 3.458 | 3 | 1103657 / 23599 / 1103657 |
| dask | 2 | 3 | 2.264 | 1.034 | 575.7 | 3.424 | 3 | 1103657 / 23599 / 1103657 |

## Conclusiones dentro del alcance medido

1. **En esta operación, muestra y equipo, Dask fue más rápido y usó menos memoria observada en ambas configuraciones.** Con un worker, la mediana total fue 3,022 s frente a 16,344 s; con dos, 2,384 s frente a 15,153 s. No hay una configuración medida en la que Spark gane en tiempo o memoria. No sería correcto inventar una recomendación favorable a Spark para un tamaño o escenario no probado.
2. **Para minimizar latencia en esta grilla, Dask con dos workers fue la mejor configuración medida.** Frente a Dask con uno, redujo la mediana total un 21,1 %, con un pico de memoria del motor un 35,5 % mayor y una mediana de CPU s un 12,5 % mayor. Si se prioriza memoria/CPU sobre unos 0,638 s de reducción por ejecución, Dask con un worker fue la alternativa de menor consumo medida.
3. **Añadir un segundo worker a Spark tuvo un beneficio temporal modesto en esta prueba.** La mediana bajó un 7,3 %, mientras el pico aumentó un 42,1 % y CPU s un 31,3 %. Sus rangos de tiempo se solapan: tres repeticiones no permiten afirmar una diferencia estadísticamente significativa ni atribuirla exclusivamente al worker adicional.
4. La diferencia no es solo el proceso externo de lanzamiento: las medianas del intervalo interno de operación también favorecieron a Dask (1,752/1,034 s frente a 11,409/10,065 s). Ese intervalo todavía incluye planificación, lectura, comunicaciones y materialización; **no permite aislar cuál de esos componentes causa la diferencia**.
5. Los resultados **no demuestran superioridad general de Dask**. No se midieron datos mayores, lectura MongoDB dentro del tiempo, salida persistente, joins, fallos de nodos, máquinas separadas ni múltiples consultas dentro de una sesión Spark ya inicializada. No se justifica cambiar la arquitectura Spark exigida por la guía a partir de este único benchmark. El uso productivo del conector MongoDB y las agregaciones de Fase 4 se conserva.

Todas las ejecuciones procesaron 1.103.657 registros, generaron 23.599 celdas y sumaron 1.103.657; las comparaciones exactas pasaron. Los workers realmente utilizados coincidieron con los configurados. No hubo tareas fallidas, reintentos de tareas ni OOM kills en la serie formal. Los calentamientos permanecen visibles y excluidos de las medianas, rangos y picos comparativos.

El máximo observado de la suma de **todos los contenedores activos**, incluyendo MongoDB, API y Jenkins, fue **2.314,19 MiB (~2,260 GiB)**. Sus máximos individuales fueron MongoDB 648,3 MiB, API 43,57 MiB y Jenkins 465,0 MiB; no necesariamente simultáneos. Están calculados desde las mismas muestras en [resources.json](benchmark/resources.json). Windows tenía 655.508 KiB libres en una lectura durante los pilotos; no se midió continuamente la memoria total del host ni se atribuye toda su presión al benchmark.

Limitaciones adicionales: orden de bloques fijo con inversión de motores entre C1/C2, cuotas sin afinidad a cores físicos, cachés del sistema operativo sin vaciar y aplicaciones Windows ajenas al experimento. Las muestras de memoria cortas de Dask (3–4 frames en las ejecuciones medidas) tienen menor resolución temporal efectiva para detectar picos que las ejecuciones largas. Se reportan máximos **observados**, no máximos absolutos garantizados.

## Pruebas, incidencias y estado final

| Comprobación ejecutada | Resultado real |
|---|---|
| Pytest local `tests tests_benchmark` en `.venv` | 59 aprobadas en 1,82 s |
| Imagen API de pruebas, barrera pytest existente | 58 aprobadas en 0,43 s |
| Spark: fixture de fronteras y fixture MongoDB/conector/idempotencia | 2 aprobadas; JUnit 16,282 s; comando 25,656 s |
| Fixture Dask dentro de imagen de pruebas | 1 aprobada en 0,73 s |
| Imagen completa de pruebas de ingesta + fixture Dask | 16 aprobadas en 2,92 s, sin omisiones; solo datos de prueba, sin Kaggle real |
| Integración API/MongoDB | 4 aprobadas en 0,69 s |
| Endpoints desplegados, incluyendo errores de validación | Smoke HTTP aprobado |
| Serie formal, cuatro combinaciones | 16 ejecuciones válidas; todas las tuplas de celdas iguales |
| Regeneración de tablas/resumen/recursos desde artefactos publicados | Archivos idénticos byte a byte |
| Dependencias locales | `pip check`: sin incompatibilidades |
| Hashes del código usado en la serie | Coinciden con los archivos de implementación al cierre |

Las pruebas nuevas cubren extremos de coordenadas, frontera cercana a cero, rechazo de coordenadas no finitas, celdas duplicadas, detección de resultados distintos con la misma suma, unidades de memoria y salida ANSI de Docker. Spark y Dask se comprueban además contra los mismos puntos conocidos. Las comprobaciones de datos reales son automáticas en cada ejecución del benchmark.

Se construyeron y probaron realmente las imágenes modificadas. Las pruebas pequeñas están conectadas a los puntos de entrada existentes de CI: pytest API, suite Spark y etapa unitaria del job de ingesta. **No se lanzó un nuevo build Jenkins completo ni un despliegue en esta fase**; sus comandos de pruebas se ejecutaron directamente en Docker. No se presenta esa ejecución directa como validación nueva del job Jenkins. El benchmark formal no se añadió al despliegue automático.

Al cierre se verificaron los ocho servicios habituales saludables, sin `OOMKilled`, y se retiraron los servicios temporales del benchmark. La API siguió respondiendo y no fue desplegada de nuevo. Las colecciones analíticas y la muestra original se conservan. La guía original mantiene SHA-256 `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`.

Incidencias de diagnóstico, **excluidas de la serie formal**:

1. Docker Desktop estaba detenido; se inició y se recuperaron los servicios sin borrar volúmenes.
2. Primer piloto: `.env` aportaba `COMPOSE_PROJECT_NAME=parcialbigdata`, con prioridad sobre el nombre del YAML. El inventario incluía contenedores productivos y la lectura de contadores falló al intentar usar Python en uno que no lo incluye. Se fijó `--project-name pbd-benchmark` expresamente. Solo se retiraron los servicios temporales; se restauró el cómputo habitual.
3. Segundo piloto: la agregación Dask coincidió, pero la captura de memoria no tenía muestras válidas por códigos ANSI emitidos por `docker stats` aun con stdout redirigido. La ejecución fue rechazada; se corrigió el parser y se añadió prueba unitaria. No se inventó un pico.
4. Tercer piloto: Spark dividía los archivos adicionalmente por su mínimo predeterminado de particiones. La aserción de ocho particiones rechazó el resultado. Se fijó el mínimo por lectura y se repitió el piloto completo.
5. Cuarto piloto: las cuatro combinaciones y sus calentamientos aprobaron. Después se ejecutó la serie formal independiente. No se mezclaron sus tiempos con los de las 12 repeticiones medidas.

## Evidencias y archivos

- [Tablas reproducibles](benchmark/tablas.md), [métricas de las 16 ejecuciones](benchmark/results.json), [resumen calculado](benchmark/summary.json), [manifiesto de entrada](benchmark/manifest.json) y [entorno/código](benchmark/environment.json).
- `docs/benchmark/samples/`: lecturas brutas de recursos versionables; no contienen accidentes ni secretos.
- `reports/phase5/formal-20261001/`: logs completos, eventos Spark, métricas por ejecución y evidencias locales; los pilotos quedan en directorios separados. `reports` continúa ignorado por Git.
- Implementación: `benchmark/{snapshot,common,dask_grid,run,metrics}.py`, `ci/compose.benchmark.yml`, `scripts/benchmark.py`, `scripts/summarize_benchmark.py`.
- Pruebas: `tests/test_benchmark.py`, `tests_benchmark/test_dask_grid.py` y fixture adicional de `tests_processing/test_aggregates.py`. Las imágenes de pruebas copian estos módulos. Las pruebas pequeñas se incorporan a las barreras existentes; la serie formal se ejecuta explícitamente y no dentro del despliegue automático.

## Reproducción en Windows CMD

Con la ingesta y Fase 4 existentes, Docker iniciado y sin otros jobs pesados:

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pip install -r requirements\local.txt
docker compose start --wait
python -m pytest tests tests_benchmark -q
python scripts\benchmark.py --label revision-fase5 --repeats 3
python scripts\summarize_benchmark.py reports\phase5\revision-fase5 --output reports\phase5\revision-fase5\tablas
docker compose ps
python scripts\smoke_geo.py http://127.0.0.1:5000
```

Usar una etiqueta nueva en cada serie: el arnés rechaza sobrescribir un directorio de evidencia existente. Desde otro equipo se deben construir primero las imágenes y completar las fases 3–4 según README; este benchmark no descarga el dataset por su cuenta. En el equipo actual las imágenes y volúmenes ya existen. La copia persistente se crea solo si falta y se verifica antes de reutilizarla.

Para reconstruir las tablas de los resultados publicados **sin repetir el benchmark**:

```cmd
python scripts\summarize_benchmark.py docs\benchmark --output reports\phase5\tablas-reconstruidas
```

Pruebas Docker, secuenciales y fuera de cualquier medición:

```cmd
docker compose build api-tests spark-master
docker compose run --rm --no-deps api-tests
docker compose up -d --no-deps --no-build --wait spark-master spark-worker
python scripts\run_spark.py --test --label phase5-review-tests
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml build ingestion-tests
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion-tests python -m pytest tests_benchmark -q
```

El último comando prueba datos conocidos; no inicia la ingesta ni usa Kaggle. Si se interrumpe manualmente la consola y no alcanza a completarse la restauración, comprobar que los contenedores `pbd-benchmark` estén detenidos antes de iniciar de nuevo el cómputo habitual:

```cmd
docker compose --project-name pbd-benchmark --env-file .env -f ci\compose.benchmark.yml down
docker compose start --wait
```

No usar `down -v`. No se añadieron dependencias Python globales ni herramientas SIG/ML. Las tablas son suficientes para estas cuatro combinaciones; se evita una gráfica que oculte las repeticiones o sugiera significancia estadística no comprobada.

## Git y límite de fase

Rama de trabajo: `develop/final-delivery`. Se prepara **un único commit local de cierre**, después de las pruebas, con mensaje `feat(benchmark): compare Dask and Spark grids with reproducible measurements`. Incluye también los documentos pendientes del cierre aprobado de Fase 4. No se hicieron commits intermedios, push ni PR. `main` y la referencia local `origin/main` se conservan en `2ec352a90f7cd37488bf040f6da13a2435a82350`; no se reescribió historial ni se consolidaron commits todavía. El hash del commit de cierre se informa al equipo después de crearlo.

Las evidencias de medición pequeñas son versionables; `.env`, credenciales, `.venv`, CSV, cachés de datos y logs locales siguen excluidos. Se revisa el contenido preparado antes del commit con el hook de secretos y rutas del proyecto.

Permanecen pendientes el checkout remoto, webhook, entrega e informe académico final. No se avanzó a esas actividades. Se detiene el desarrollo para revisión y aprobación del equipo.

Fuentes para la configuración, no para las conclusiones experimentales: [lectura CSV de Dask](https://docs.dask.org/en/stable/generated/dask.dataframe.read_csv.html), [agrupación Dask y split_out](https://examples.dask.org/dataframes/02-groupby.html), [particiones y AQE de Spark 3.5.8](https://spark.apache.org/docs/3.5.8/sql-performance-tuning.html).
