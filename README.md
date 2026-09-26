# US Accidents: infraestructura geoespacial

Estado de desarrollo: infraestructura de fase 1 integrada en `main` y trabajo local de fase 2 sobre Jenkins e integración continua en `develop/final-delivery`. La API implementa únicamente `GET /health`. No hay descarga de Kaggle, ingesta, agregaciones ni consultas geoespaciales. Repositorio privado: [DavierGonz/ParcialBigData](https://github.com/DavierGonz/ParcialBigData). No se publicarán entregas intermedias; el siguiente push y PR serán los de la versión final completa.

Fuente principal: `Insumos/Trabajo_Big_Data_Geoespacial-1.docx`, leído íntegramente y conservado sin modificaciones. Dataset confirmado: [US Accidents de Kaggle](https://www.kaggle.com/datasets/sobhanmoosavi/us-accidents). La trazabilidad está en [docs/requisitos.md](docs/requisitos.md); las decisiones y fuentes están en [docs/arquitectura.md](docs/arquitectura.md). Resultados: [informe de fase 1](docs/informe-fase1.md) e [informe de fase 2](docs/informe-fase2.md).

## Preparación desde cero en Windows CMD

Requisitos: Python 3.10 de 64 bits, Docker Desktop iniciado con motor Linux/WSL2, Docker Compose moderno con `--wait`, conexión a Internet para descargar imágenes y dependencias, y espacio libre. No se requiere Java, MongoDB, Spark o Dask instalados en Windows. Se comprobó Python local 3.10.11; los contenedores API/Dask usan 3.10.20. No usar el Python 3.14 predeterminado para este proyecto.

En una ventana **CMD**, desde la raíz existente:

```cmd
cd /d D:\Proyects\ParcialBigData
py -3.10 --version
docker version
docker compose version
if not exist .venv\Scripts\python.exe py -3.10 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements\dev.txt
python -m pip check
python scripts\init_env.py
python -m pytest -q
```

Si Docker está apagado, abrir Docker Desktop o ejecutar `docker desktop start`. Esperar a que `docker version` muestre también la sección Server. `init_env.py` genera contraseñas aleatorias solo en `.env`, que está excluido del control de versiones; nunca sobrescribe un archivo existente. `.env.example` es una plantilla sin secretos. No copiarla sobre el `.env` generado.

No se instala ningún paquete Python globalmente. Cada Dockerfile instala sus propias dependencias: los contenedores no montan ni reutilizan `.venv`.

## Levantar y verificar

Después de la preparación, un comando construye las pruebas, exige que pasen, levanta los ocho servicios y verifica sus conexiones:

```cmd
scripts\start.cmd
```

Para ejecutar manualmente los mismos pasos, **detenerse ante cualquier error**:

```cmd
docker compose config --quiet
docker compose build api-tests
docker compose run --rm --no-deps api-tests
docker compose up -d --build --wait --wait-timeout 300
python scripts\verify_infra.py
```

La primera construcción descarga imágenes y dependencias de software, nunca el dataset. Las siguientes reutilizan las capas Docker. Las imágenes base están fijadas por versión y digest; los archivos `requirements/*.txt` fijan las dependencias directas y transitivas.

```cmd
docker compose ps
curl.exe --fail http://127.0.0.1:5000/health
docker compose run --rm --no-deps api-tests
python scripts\verify_infra.py
docker compose exec -T spark-master /opt/spark/bin/spark-submit /opt/smoke_spark.py
docker compose exec -T jenkins docker version
docker compose exec -T jenkins docker compose version
docker stats --no-stream
docker compose logs --tail 80 api spark-worker dask-worker-1 dask-worker-2
```

Respuesta esperada de la API: `{"service":"us-accidents-api","status":"ok"}`. `/health` verifica que Flask responde; **no certifica que MongoDB o los clústeres estén listos**. `verify_infra.py` sí exige ocho servicios saludables, el índice y validador de MongoDB, ejecución en ambos workers Dask, registro del worker Spark, lectura real por MongoDB Spark Connector y acceso Docker desde Jenkins. Son pruebas pequeñas de infraestructura, sin datos de Kaggle.

| Servicio | Acceso desde Windows | Acceso entre contenedores |
|---|---|---|
| API | http://127.0.0.1:5000/health | `api:5000` |
| Jenkins | http://127.0.0.1:8080 | Red `ci` |
| Spark master UI | http://127.0.0.1:8081 | `spark-master:8080`, RPC `spark-master-internal:7077` |
| Dask dashboard | http://127.0.0.1:8787 | `dask-scheduler:8786` |
| MongoDB | Sin puerto publicado | `mongodb:27017` |

Los puertos publicados se enlazan a `127.0.0.1`. Se pueden cambiar en `.env`; los puertos internos permanecen constantes. `docker compose config --quiet` valida sin imprimir credenciales. Evitar compartir la salida completa de `docker compose config` o `docker inspect`, porque contienen variables sensibles.

## Detener y volver a iniciar sin perder datos

```cmd
docker compose stop
docker compose start --wait
python scripts\verify_infra.py
```

Para retirar contenedores y redes y conservar los volúmenes:

```cmd
docker compose down
docker compose up -d --wait --wait-timeout 300
```

No usar `down -v` ni eliminar los volúmenes: contienen MongoDB, Jenkins, la futura caché del dataset y áreas temporales de los motores. No se ha descargado ningún dataset en esta fase. Mantener `COMPOSE_PROJECT_NAME=parcialbigdata` evita crear otra familia de volúmenes por accidente.

## Desarrollo local

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pytest -q
python -m flask --app api:create_app run --host 127.0.0.1 --port 5001
```

En otra ventana CMD, `curl.exe --fail http://127.0.0.1:5001/health`. Detener Flask con Ctrl+C; salir del entorno con `deactivate`. El puerto 5001 evita colisionar con la API Docker. Gunicorn se usa únicamente dentro de Linux.

Las entradas de dependencias son `requirements/*.in`; los `.txt` son los conjuntos resueltos para Python 3.10. Dask y PySpark no se instalan en el entorno local durante esta fase: se ejecutan en sus contenedores. Para actualizar dependencias deliberadamente, usar `pip-tools==7.5.1` dentro de `.venv` o en un contenedor Python temporal, regenerar los `.txt` y repetir las pruebas. El pin de Colorama en desarrollo cubre también Windows. `requirements/local-tooling.txt` registra adicionalmente el entorno local de desarrollo y las herramientas de resolución utilizadas; se puede reproducir con `python -m pip install -r requirements\local-tooling.txt` dentro de `.venv`. No regenerar dependencias automáticamente durante cada arranque.

## Jenkins local y futura conexión con GitHub

Jenkins conserva el asistente inicial y la autenticación. Para ver la contraseña inicial **solo en su terminal privada**:

```cmd
docker compose exec -T jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Abrir http://127.0.0.1:8080, desbloquear Jenkins, usar los plugins ya incluidos y crear su cuenta de administrador. La contraseña inicial desaparece después de completar el asistente; no copiarla al repositorio. El volumen `jenkins_home` conserva usuarios, configuración y futuras credenciales.

La imagen incluye Pipeline, Git, GitHub y JUnit; sus 72 plugins y dependencias están fijados en `docker/jenkins/plugins.txt`. Tiene un ejecutor con etiqueta `local-docker`, Docker CLI y Compose. El Jenkinsfile de fase 2 realiza checkout, construcción, pytest obligatorio, integración de los motores, candidata aislada y despliegue local de la API con recuperación ante fallo. No publica código ni imágenes en servicios remotos. La configuración, comandos y pruebas negativas se explican en [docs/ci-local.md](docs/ci-local.md).

El repositorio ya está creado y el PR #1 está integrado. Jenkins puede ejecutar commits locales sin subirlos a GitHub mediante `scripts/jenkins_local.py`. En la entrega final se configurará el job desde SCM y el disparador GitHub. El webhook futuro será `<URL-HTTPS-publica-de-Jenkins>/github-webhook/`: GitHub no puede acceder a `localhost`. La exposición HTTPS autenticada/túnel y validación de eventos quedan pendientes; no se ha abierto ningún puerto público.

Las credenciales Kaggle se registrarán después en Jenkins Credentials (por ejemplo, archivo secreto `kaggle-api-token`), nunca en `.env.example`, código ni imágenes. El futuro job de descarga tendrá salida a Internet y acceso a `dataset_cache`; Dask y MongoDB permanecen en una red interna. Se necesitarán manifiestos de versión/checksum y marcas de procesamiento exitoso para reutilizar la caché de forma correcta: el volumen por sí solo no implementa idempotencia.

Jenkins accede al socket del Docker Desktop local mediante grupo 0, conservando el usuario `jenkins`. Esto da control amplio sobre el motor; ejecutar solo jobs y ramas confiables del equipo. No ejecutar pull requests externos con este socket. Es una decisión para el laboratorio de un solo equipo; un entorno compartido requeriría un agente aislado. Las futuras construcciones usarán contextos Docker, no bind mounts de rutas Windows desde el contenedor Jenkins.

## Diagnóstico

- Si un puerto está ocupado, cambiar su variable en `.env` y volver a levantar. Consultar `docker compose ps` y `docker compose logs --tail 100 NOMBRE_SERVICIO`.
- Si faltan recursos, cerrar aplicaciones ajenas al proyecto antes de construir. Los límites suman 6,875 GiB; el consumo en reposo es menor, pero los jobs y las construcciones también necesitan memoria. No se ha validado todavía una carga de un millón de accidentes.
- MongoDB inicializa usuarios, validador e índice solamente con el volumen vacío. Cambiar contraseñas en `.env` no modifica los usuarios existentes; hay que rotarlos expresamente mediante MongoDB. Conservar el `.env` local junto con una copia segura de sus datos.
- Los workers Dask derraman a disco en sus volúmenes `/scratch`. El límite de cada proceso es 768 MiB, dentro de un contenedor de 1 GiB; Spark anuncia 1 GiB al master, con ejecutor de 768 MiB y contenedor de 1,5 GiB.
- El arranque saludable de Jenkins no implica que su asistente haya sido completado. La conexión real GitHub → Jenkins requiere configuración posterior.

## Estructura

```text
ParcialBigData/
  Insumos/                  documento original, intacto y excluido
  .venv/                    entorno local, excluido
  api/                      factoría Flask y entrada WSGI
  ci/                       candidata, etapas CI y fallos de prueba explícitos
  tests/                    contrato de GET /health
  docker/
    api/ dask/ mongo/ spark/ jenkins/
  requirements/             entradas y dependencias fijadas
  scripts/                  configuración local, arranque y verificaciones
  docs/                     arquitectura, requisitos e informe de fase
  docker-compose.yml
  Jenkinsfile
  .env.example
  .gitignore
  .dockerignore
  .gitattributes
  pytest.ini
  README.md
```

El asistente tiene autorización para gestionar Git y GitHub. Se utilizan `main` y ramas de trabajo, commits que identifican su autoría real y pull requests que no se integran hasta la aprobación de la fase. La [política de Git](docs/git-workflow.md) explica las comprobaciones antes de cada commit y cómo activar el hook después de clonar. No se continuará con la fase siguiente hasta su revisión y aprobación.
