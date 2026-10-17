# US Accidents: procesamiento geoespacial y CI/CD

**Reanudar este equipo tras reiniciar:** abrir Docker Desktop, esperar motor listo y ejecutar `scripts\resume_local.cmd`. Conserva Atlasvial y los datos. Compose principal publica Compass exclusivamente en **127.0.0.1:27018**, también en despliegues Jenkins, sin interferir con MongoDB de Windows. No requiere un override local. [Arranque local y límites del túnel](docs/arranque-local.md).

**Interfaz web Atlas vial:** mapa Leaflet, consulta por punto/radio y tarjetas de accidentes con distancias en **http://127.0.0.1:5000/**. Con la infraestructura existente iniciada, `scripts\start_ui.cmd` construye, prueba y activa únicamente Flask. [Guía de uso, pruebas y demostración](docs/interfaz-web.md). Esta ampliación permanece local sin commit/push hasta autorización.

**Kaggle API → caché → Dask → MongoDB → Spark → MongoDB → Flask**. GitHub envía eventos HTTPS a una pasarela HMAC que reenvía solo el webhook a Jenkins; la administración permanece en localhost.

Resultados reales: 7.728.394 filas originales, muestra de **1.103.657 accidentes**, **23.599 celdas** y **2.660 grupos temporales**. Repositorio privado [DavierGonz/ParcialBigData](https://github.com/DavierGonz/ParcialBigData). Entrega en `develop/final-delivery`; merge a `main` sujeto a revisión.

Entregables: [matriz](docs/matriz-final.md), [informe académico](docs/informe-academico.pdf), [cierre técnico](docs/informe-final.md), [benchmark](docs/informe-fase5.md), [sustentación](docs/sustentacion.md).

## Preparar Windows y clonar

Requisitos: Windows 64 bits, Python **3.10**, Git, GitHub CLI (`gh`), Docker Desktop Linux/WSL2 y Compose con `--wait`. Equipo probado: 16 GB RAM, Docker aproximadamente 7,64 GiB. Internet y espacio para imágenes, CSV de 3,06 GB, ZIP y volúmenes. No instalar Java/MongoDB/Spark/Dask globalmente. El repositorio privado requiere acceso de lectura; configurar deploy key/webhook requiere administración.

**Windows CMD**, nueva instalación (no clonar encima de una carpeta existente):

```cmd
gh auth login
gh auth setup-git
git clone --branch develop/final-delivery https://github.com/DavierGonz/ParcialBigData.git D:\Proyects\ParcialBigData
cd /d D:\Proyects\ParcialBigData
py -3.10 --version
docker version
docker compose version
py -3.10 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements\local.txt
python -m pip check
python scripts\init_env.py
python -m pytest tests tests_benchmark -q
```

Después del merge aprobado puede clonarse `main`. En el equipo existente basta activar `.venv`. Si Docker está apagado: abrir Docker Desktop o `docker desktop start`; esperar Server en `docker version`. `init_env.py` genera contraseñas aleatorias sin sobrescribir `.env`. No copiar la plantilla sobre él. Cada Dockerfile instala sus dependencias; no usa `.venv`.

## Levantar y verificar

```cmd
scripts\start.cmd
docker compose ps
curl.exe --fail http://127.0.0.1:5000/health
python scripts\verify_infra.py
```

El script valida Compose, construye/ejecuta pytest, levanta ocho servicios y verifica MongoDB/GeoJSON/2dsphere, tareas en ambos workers Dask, conector Spark y Docker desde Jenkins. No descarga Kaggle. `/health` solo verifica Flask: `{"service":"us-accidents-api","status":"ok"}`.

| Servicio | Acceso local | Versión / límite |
|---|---|---|
| MongoDB | Solo red interna | 8.0.16 / 768 MiB |
| Spark master / worker | http://127.0.0.1:8081 | 3.5.8; conector 10.7.0 / 1.024 y 1.536 MiB |
| Dask scheduler / 2 workers | http://127.0.0.1:8787 | 2025.5.1 / 384 y 2 × 1.024 MiB |
| Flask | http://127.0.0.1:5000 | 3.1.3 / 256 MiB |
| Jenkins | http://127.0.0.1:8080 | 2.568.3 JDK21 / 1.024 MiB |

Puertos enlazados a localhost, configurables en `.env`. Límites base: 6,875 GiB. Volúmenes persistentes para datos/caché/Jenkins/scratch. MongoDB inicializa usuarios solo con volumen vacío: modificar `.env` no rota usuarios existentes. No ejecutar cargas pesadas Dask/Spark ni benchmark/Jenkins simultáneamente.

## Configurar credenciales y Jenkins

Abrir http://127.0.0.1:8080, desbloquear con la contraseña inicial, visible **solo en su terminal privada**:

```cmd
docker compose exec -T jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Usar los plugins incluidos y completar el asistente creando administrador. Después:

```cmd
python scripts\jenkins_remote.py login
if not exist secrets mkdir secrets
notepad secrets\kaggle-token.txt
python scripts\jenkins_remote.py setup
```

Guardar únicamente el token Kaggle, sin comillas; alternativa: `secrets\kaggle.json` legacy. Nunca poner secretos en comandos ni Git. `login` pide contraseña sin eco. `setup` registra en Jenkins `.env`, Kaggle, deploy key SSH **solo lectura** y secreto HMAC; obtiene claves del host GitHub por HTTPS. Requiere `gh` autenticado con permisos del repositorio. Respaldos locales en `secrets/`, ignorados por Git/Docker.

Jobs: `parcialbigdata-main` lee main; `parcialbigdata-validation` lee develop; ambos usan el Jenkinsfile final. `parcialbigdata-ingestion` lee develop, se inicia explícitamente y no despliega Flask. Después del merge puede cambiarse su Branch Specifier a `*/main`. Jenkins tiene un ejecutor y acceso amplio al socket Docker: solo código/usuarios de confianza, sin PR externos. Helpers/Jenkinsfiles `*-local` son históricos y no participan en el flujo final.

## Ejecutar la ingesta

Esperar `SUCCESS` antes de Spark/pipeline API. Sustituir `N` por el build devuelto:

```cmd
python scripts\jenkins_remote.py run --job parcialbigdata-ingestion
python scripts\jenkins_remote.py status --job parcialbigdata-ingestion --number N
```

Descarga completa v13 automática, hashes/metadatos en `dataset_cache:/data/us-accidents-v13`. Repeticiones verifican y reutilizan caché/carga. Dask: bloques de 16 MiB, limpieza de coordenadas, upserts de 500. Muestra BLAKE2b por ID/semilla módulo 7; mínimo un millón limpio. [Reglas](docs/ingesta.md), [resultados](docs/informe-fase3.md).

Verificación sin credencial ni descarga, con caché existente:

```cmd
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion python -m ingestion.run --verify-only
```

En Jenkins, `VALIDATE_ONLY=true` ejecuta fixtures; `FORCE_ETL=true` repite upserts, normalmente innecesario. No actualizar versión Kaggle sin revisar esquema/muestra; una versión inesperada causa fallo explícito.

## Ejecutar Spark y consultar Flask

```cmd
python scripts\run_spark.py --label revision-spark
python scripts\smoke_geo.py http://127.0.0.1:5000
curl.exe --fail "http://127.0.0.1:5000/accidents/near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail "http://127.0.0.1:5000/accidents/geo-near?lat=32.81517&lon=-116.914566&radius_m=1000&limit=2"
curl.exe --fail -H "Content-Type: application/json" --data-binary @examples\polygon.json http://127.0.0.1:5000/accidents/within
curl.exe --fail "http://127.0.0.1:5000/analytics?kind=hotspots&limit=3"
```

Spark publica grilla, hora/fecha/mes y 50 hotspots en `analytics_*`; reutiliza resultados completos de la misma huella. `--force` recalcula solo Spark. Antes de publicar, `/analytics` devuelve 503. [Contrato API, límites y errores](docs/api-geoespacial.md).

## Webhook HTTPS y pipeline final

Después de preparar Jenkins y los datos:

```cmd
docker compose -f docker-compose.yml -f ci/compose.webhook.yml up -d --build --wait webhook tunnel
python scripts\jenkins_remote.py setup-webhook
python scripts\jenkins_remote.py run --job parcialbigdata-validation
```

Esperar el fin del build; verificar con `python scripts\verify_final_build.py N --job parcialbigdata-validation`. Checkout privado SSH → build → pytest → Mongo/Dask/Spark → fixtures analíticos/API → construcción candidata → HTTP → promoción → HTTP. Fallo previo bloquea promoción; fallo posterior restaura imagen anterior. No repite descarga/ETL.

Pasarela HMAC-SHA256, filtro de repositorio/ramas y deduplicación persistente. Solo expone `/github-webhook/` y `/health`; no reenvía administración. Túnel Cloudflare sin abrir router, TLS verificado. 128 MiB adicionales por pasarela/túnel; total permanente 7,125 GiB, sin ampliar Docker.

**Quick Tunnel es temporal:** URL puede cambiar al reiniciar. Ejecutar `setup-webhook` tras cada reinicio y comprobar entrega ping; mantener host encendido. No hay SLA; dominio estable requeriría cuenta/túnel nombrado. Push de main activa su job cuando cambia esa rama; develop activa validación. [Seguridad y recuperación](docs/ci-final.md).

## Benchmark y pruebas

Sin jobs ni cargas pesadas simultáneas, con etiqueta nueva:

```cmd
python scripts\benchmark.py --label nueva-serie --repeats 3
python scripts\summarize_benchmark.py reports\phase5\nueva-serie --output reports\phase5\nueva-serie\tablas
```

El arnés pausa cómputo habitual, ejecuta uno/dos workers por motor secuencialmente y restaura servicios; compara todas las celdas. Para regenerar tablas sin medir otra vez y probar:

```cmd
python scripts\summarize_benchmark.py docs\benchmark --output reports\phase5\tablas-reconstruidas
python -m pytest tests tests_benchmark tests_ingestion -q
python scripts\run_spark.py --test --label revision-tests
docker compose build api-tests
docker compose -f docker-compose.yml -f ci/compose.integration.yml run --rm --no-deps api-integration
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml build ingestion-tests
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion-tests
```

Las pruebas locales omiten integración Linux/Docker explícitamente; los comandos Docker sí la ejecutan. [Benchmark y limitaciones](docs/informe-fase5.md). [Sustentación](docs/sustentacion.md), sin commit de demostración ejecutado.

## Detener, reanudar y diagnosticar

Respaldar `.env`/credenciales de forma segura junto con los volúmenes. No eliminar volúmenes para detener:

```cmd
docker compose -f docker-compose.yml -f ci/compose.webhook.yml stop
docker compose -f docker-compose.yml -f ci/compose.webhook.yml start --wait
python scripts\jenkins_remote.py setup-webhook
python scripts\verify_infra.py
docker stats --no-stream
```

Sin webhook: `docker compose stop` y `docker compose start --wait`. Diagnóstico: `docker compose logs --tail 100 api`, servicio afectado o consola autenticada Jenkins. No compartir configuración/inspect completos: contienen variables sensibles; validar con `docker compose config --quiet`. Si rollback falla, `.ci/deployment.pending` bloquea nuevos builds; no borrar workspace y seguir [recuperación](docs/ci-final.md).

## Archivos y reproducción

Implementación en `api/`, `ingestion/`, `processing/`, `benchmark/`, `webhook/`; fixtures `tests*/`; infraestructura `docker/`, `ci/`, `requirements/`; operación `scripts/`; informes `docs/`.

`.env`, `.venv`, `secrets/`, datasets, cachés, `reports/` e `Insumos/` no se versionan. El original permanece intacto. `docs/benchmark/` contiene métricas, no accidentes. Activar control de secretos: `git config core.hooksPath .githooks`.

Reproducción: nuevo checkout/venv/credenciales/volúmenes **en el mismo Windows/Docker**, reutilizando caché de imágenes/paquetes. No demuestra segundo equipo físico. [Alcance/evidencia](docs/informe-final.md). `python scripts\reproduce_clean.py` automatiza fixtures y pausa servicios; rechaza sobrescribir evidencia existente. `python scripts\reproduce_data.py` completa ese checkout con descarga independiente, ETL, Spark y HTTP; requiere el token documentado en `secrets/kaggle-token.txt`. Ambos se ejecutaron en el cierre; los volúmenes de reproducción quedan detenidos.

Regenerar el informe dentro de `.venv`:

```cmd
python -m pip install -r requirements\report.txt
python scripts\build_report.py
```

Fuentes: guía original (hash en matriz), [Kaggle](https://www.kaggle.com/datasets/sobhanmoosavi/us-accidents), informes [1](docs/informe-fase1.md), [2](docs/informe-fase2.md), [3](docs/informe-fase3.md), [4](docs/informe-fase4.md), [5](docs/informe-fase5.md). Sus pendientes son históricos; la matriz final indica estado actual.

prueba  1