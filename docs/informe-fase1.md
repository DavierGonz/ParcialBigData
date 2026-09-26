# Informe de finalización de fase 1

Verificación realizada el 26 de septiembre de 2026 en `D:\Proyects\ParcialBigData`. La infraestructura y la API mínima están implementadas y verificadas. Los ocho servicios quedan encendidos y saludables para revisión. No se ha iniciado ninguna fase de ingesta, procesamiento del dataset ni consultas geoespaciales.

Actualización posterior del mismo proyecto: el equipo autorizó la gestión de Git y GitHub. Se creó el repositorio privado [DavierGonz/ParcialBigData](https://github.com/DavierGonz/ParcialBigData), con `main` como base de control de versiones y `feat/phase-1-infrastructure` para revisar esta fase. Esto no implica aprobación ni integración de la infraestructura. La política vigente está en [git-workflow.md](git-workflow.md); los resultados de infraestructura de este informe corresponden a las pruebas anteriores, sin presentar una nueva ejecución de Jenkins.

## Arquitectura implementada

Docker Compose administra MongoDB, Spark master y un worker, Dask scheduler y dos workers, Flask y Jenkins. Existe además un contenedor efímero `api-tests`, activado bajo perfil de pruebas. El [diagrama y las decisiones](arquitectura.md) distinguen las conexiones verificadas del flujo de datos futuro.

MongoDB tiene autenticación, usuario de aplicación limitado a `us_accidents`, colección vacía `accidents`, validador de puntos GeoJSON e índice real `location_2dsphere`. Spark tiene MongoDB Spark Connector incorporado durante la construcción de su imagen; se comprobó una lectura distribuida de la colección vacía. Dask ejecutó una tarea pequeña en cada uno de sus dos workers. Flask sirve exclusivamente `GET /health` mediante Gunicorn.

Las redes son `backend` interna, `frontend` para publicar API y paneles en loopback, y `ci` para Jenkins. MongoDB y los workers no publican puertos. Ocho volúmenes conservan MongoDB, Jenkins, caché del dataset y temporales de los motores. `.env` contiene credenciales locales aleatorias, está ignorado y no entra en contextos de construcción. No se configuró ninguna credencial Kaggle.

Jenkins tiene Docker CLI, Compose y plugins Pipeline/Git/GitHub con sus dependencias fijadas. Se conserva el asistente de seguridad para que el equipo cree su administrador. El Jenkinsfile es un **esqueleto ejecutable de CI**, pendiente de asociar al repositorio: checkout, build de pruebas, pytest obligatorio y build de imagen candidata. No hay despliegue automático activo. No se ejecutó el Jenkinsfile ni su checkout; la autorización posterior para Git permitió publicar la rama de revisión, pero no constituye validación del job Jenkins.

## Versiones y entorno

| Componente | Versión observada o fijada |
|---|---|
| Windows, RAM física visible | 15,78 GiB aproximadamente, equipo anunciado de 16 GB |
| Python local en `.venv` | 3.10.11; `include-system-site-packages = false` |
| Python predeterminado encontrado | 3.14.7, no utilizado para desarrollar el proyecto |
| Docker Desktop: Engine / Compose | 29.5.3 / 5.1.4 |
| Motor Linux WSL2 | 16 CPU lógicas y 7,64 GiB disponibles para Docker |
| Python de API/Dask | 3.10.20 |
| Flask / Gunicorn / pytest | 3.1.3 / 23.0.0 / 8.4.2 |
| MongoDB | 8.0.16 |
| Spark / Scala / Java / Python | 3.5.8 / 2.12 / 17 / 3.10.12 |
| MongoDB Spark Connector / driver Java | 10.7.0 / 5.1.4 |
| Dask y distributed | 2025.5.1, misma imagen en los tres procesos |
| PyMongo | 4.15.1 |
| Jenkins | 2.568.3, JDK 21; 61 plugins fijados en la imagen |
| Docker CLI / Compose dentro de Jenkins | 29.5.3 / 5.1.4 |

Se fijaron imágenes base por digest y dependencias Python transitivas por versión. Las dependencias locales se instalaron únicamente en `.venv`; las de los contenedores se instalaron en sus imágenes. El entorno de resolución local quedó registrado en `requirements/local-tooling.txt`. La compatibilidad del conector se contrastó con [la matriz oficial de MongoDB](https://www.mongodb.com/docs/spark-connector/v10.x/) y con su POM, y luego se comprobó en ejecución.

## Archivos creados y estructura

Todo el código es nuevo; inicialmente solo estaba la carpeta `Insumos`. No se creó otra raíz. Los siguientes archivos se incorporaron a la rama de revisión tras la autorización para gestionar Git; se añadieron además `.githooks/pre-commit`, `scripts/check_staged.py` y `docs/git-workflow.md` para revisar el índice antes de cada commit:

| Ubicación | Archivos y función |
|---|---|
| Raíz | `README.md`, `docker-compose.yml`, `Jenkinsfile`, `.env.example`, `.gitignore`, `.dockerignore`, `.gitattributes`, `pytest.ini` |
| `api/` | `__init__.py` con factoría y endpoint; `wsgi.py` para Gunicorn |
| `tests/` | `test_health.py`, cuatro pruebas del contrato HTTP |
| `docker/api/` | `Dockerfile` con etapas base, test y runtime |
| `docker/dask/` | `Dockerfile` compartido por scheduler y workers |
| `docker/mongo/` | `Dockerfile`, `init.js` con usuario, validador e índice |
| `docker/spark/` | `Dockerfile`, `spark-defaults.conf`, `install_connector.py` |
| `docker/jenkins/` | `Dockerfile`, `plugins.txt`, `init.groovy` |
| `requirements/` | `api.in`, `api.txt`, `dev.in`, `dev.txt`, `dask.in`, `dask.txt`, `local-tooling.txt` |
| `scripts/` | `init_env.py`, `start.cmd`, `verify_infra.py`, `check_dask.py`, `check_spark.py`, `smoke_spark.py`, `lock_jenkins_plugins.py` |
| `docs/` | `requisitos.md`, `arquitectura.md`, este `informe-fase1.md` |

Además se generaron `.venv/`, `.env`, cachés de Python/pytest y `reports/` con evidencias locales, todos excluidos. `reports/` incluye logs de construcción, verificaciones, prueba negativa de la barrera, XML de pytest y muestras de `docker stats`; también una copia de plugins usada durante el diagnóstico. No contiene dataset descargado. El archivo de prueba fallida temporal se retiró y se reconstruyó la imagen de pruebas correcta.

El SHA-256 del documento original es idéntico antes y después:

`9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`

## Estado Docker al finalizar

| Servicio | Estado | Acceso publicado |
|---|---|---|
| mongodb | Running, healthy | Ninguno |
| spark-master | Running, healthy | http://127.0.0.1:8081 |
| spark-worker | Running, healthy | Ninguno |
| dask-scheduler | Running, healthy | http://127.0.0.1:8787 |
| dask-worker-1 | Running, healthy | Ninguno |
| dask-worker-2 | Running, healthy | Ninguno |
| api | Running, healthy | http://127.0.0.1:5000/health |
| jenkins | Running, healthy | http://127.0.0.1:8080 |

La salud de Jenkins indica que su servidor HTTP responde, no que el asistente, el repositorio, las credenciales o un pipeline hayan sido configurados. Ningún contenedor quedó marcado `OOMKilled`; la muestra previa al reinicio mostró cero reinicios automáticos en los ocho servicios.

## Pruebas ejecutadas y resultados reales

| Prueba | Resultado |
|---|---|
| `docker compose config --quiet` | Correcto |
| Construcción de las seis imágenes propias (incluida test) | Correcta con las configuraciones finales |
| `.venv` + `pip check` | Sin dependencias rotas |
| `pip check` en API y Dask | Sin dependencias rotas |
| `python -m pytest -q` local | **4 passed**, última ejecución 0,18 s |
| `docker compose run --rm --no-deps api-tests` | **4 passed**, última ejecución 0,09 s |
| `curl.exe --fail http://127.0.0.1:5000/health` | HTTP 200 y JSON esperado |
| `scripts\start.cmd` completo | Código 0; build, pytest, ocho servicios saludables y verificación completa |
| Prueba negativa temporal de pytest | **1 failed, 4 passed**, código 1 propagado por `start.cmd`; IDs de los ocho contenedores permanentes idénticos antes/después; no se llegó a `compose up` |
| MongoDB | Autenticación de aplicación, colección, validador e índice verificados |
| Dask | Dos workers registrados, una tarea fijada a cada worker devuelve 6; caché escribible desde ambos |
| Spark | Worker ALIVE, ejecutor lanzado por el worker y lectura con `format('mongodb')` completada; sin escrituras ni agregaciones |
| Jenkins → Docker | Acceso real al motor 29.5.3 y Compose 5.1.4 |
| Detención y arranque | `docker compose stop` y `docker compose start --wait` correctos |
| Verificación después del reinicio | Todas las comprobaciones de `verify_infra.py` pasan nuevamente |
| Documento original | SHA-256 sin cambios |
| Ausencia de descarga/ingesta | `accidents` contiene 0 documentos; `dataset_cache` está vacío |
| Configuración Jenkins | Un ejecutor, etiqueta `local-docker`, autenticación habilitada |
| Revisión de secretos locales | Las dos contraseñas generadas no aparecen en ninguno de los 38 archivos entregables |

La prueba negativa comprueba la barrera del arranque CMD. **No equivale a haber probado el bloqueo en Jenkins**; ese ensayo requiere ejecutar el futuro job cuando exista el repositorio. El Jenkinsfile mantiene semántica de fallo fatal por salida no cero de `sh`, y no incluye despliegue activo.

## Recursos observados

Muestras puntuales de `docker stats --no-stream`, no máximos históricos ni benchmark:

| Servicio | Sin job activo | Durante smoke de Spark |
|---|---:|---:|
| MongoDB | 193,30 MiB | 193,30 MiB |
| Spark master | 157,30 MiB | 423,40 MiB |
| Spark worker | 155,40 MiB | 316,70 MiB |
| Dask scheduler | 65,06 MiB | 64,21 MiB |
| Dask worker 1 | 97,79 MiB | 98,27 MiB |
| Dask worker 2 | 97,17 MiB | 97,24 MiB |
| Flask | 37,45 MiB | 36,07 MiB |
| Jenkins | 338,10 MiB | 337,50 MiB |
| Total aproximado | **1.141,57 MiB = 1,11 GiB** | **1.566,69 MiB = 1,53 GiB** |

En la muestra durante Spark, master y worker usaron respectivamente 25,61 % y 69,96 % de CPU según Docker; son lecturas instantáneas. Los límites permanentes suman 6,875 GiB y no incluyen BuildKit, motor Docker, WSL ni Windows. Al inicio Windows tenía unos 3,56 GiB libres; durante construcciones llegó a unos 303 MiB y, en una lectura posterior al reinicio y pruebas, había unos 1,72 GiB. No se cerraron aplicaciones ajenas ni se modificaron los límites globales de WSL/Docker.

Se recomienda liberar memoria de aplicaciones ajenas antes de construir o ejecutar las futuras cargas. El presupuesto fue suficiente para estas pruebas; no está demostrado todavía que soporte la carga final sin ajustes. No se midieron ni inventaron tiempos del dataset, muestreo o comparación Dask/Spark.

## Problemas encontrados y resolución

1. El motor Docker estaba apagado. Se inició mediante Docker Desktop y se verificó el servidor Linux.
2. Los puertos de servicios conectados solo a `backend` interna no se publicaron en esta versión de Docker. Se añadió `frontend` a API y paneles, manteniendo MongoDB y workers internos.
3. Spark master, con dos interfaces, elegía una dirección que su worker no podía alcanzar. Se fijó `spark-master-internal` como alias exclusivo de backend y dirección del master/driver.
4. El primer conjunto de plugins de Jenkins no produjo una resolución completamente coherente al fijar sus dependencias mínimas. Se pasó a Jenkins 2.568.3 y se fijaron las versiones de las 61 dependencias obligatorias actuales. La reconstrucción y el inicio posteriores funcionaron.
5. Se corrigieron grupo y permisos de `/data` para evitar dependencia del primer contenedor que inicialice el volumen. El volumen vacío creado durante las pruebas se ajustó a los mismos permisos de las imágenes finales. Un arranque nuevo obtiene estos permisos directamente de la imagen.

## Pendientes y límite de aprobación

- Queda por completar el asistente inicial de Jenkins. El repositorio ya existe y su gestión corresponde al asistente; la infraestructura sigue en revisión. Los commits del asistente se identifican con autoría de automatización, sin simular aportes de colaboradores.
- Quedan para fases posteriores: credencial y descarga automática completa de Kaggle, caché con manifiestos e idempotencia, muestreo reproducible si hace falta, ETL Dask, agregaciones Spark y colecciones de resultados, `$near`, `$geoWithin`, `$geoNear` y endpoints de negocio.
- Falta implementar y probar el pipeline completo, incluido candidato, smoke antes de promoción, despliegue, tratamiento de fallos y webhook desde GitHub. GitHub no puede alcanzar `localhost`; se necesitará una URL HTTPS accesible, que no se configuró ni expuso en esta fase.
- Falta el benchmark real de una operación pesada con dos configuraciones por motor, el informe académico final de hasta diez páginas y el ensayo de cambio en vivo.
- Falta validar la reproducción en un segundo equipo; aquí se probaron inicialización de volúmenes nuevos y ciclos de reconstrucción, recreación y reinicio en este Windows.

No hay un bloqueo técnico pendiente para revisar y usar esta infraestructura. Se detiene el trabajo al finalizar la fase 1 y se espera la revisión y aprobación del equipo antes de continuar.

## Comandos exactos de revisión en Windows CMD

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pip check
python -m pytest -q
docker compose config --quiet
docker compose ps
curl.exe --fail http://127.0.0.1:5000/health
docker compose run --rm --no-deps api-tests
python scripts\verify_infra.py
docker stats --no-stream
```

Para volver a construir y levantar con la barrera de pruebas:

```cmd
scripts\start.cmd
```

Para detener conservando datos:

```cmd
docker compose stop
```

Para iniciar nuevamente y verificar:

```cmd
docker compose start --wait
python scripts\verify_infra.py
```

El [README](../README.md) contiene la preparación desde cero, activación CMD, generación de `.env`, desarrollo local, acceso inicial a Jenkins y diagnóstico.
