# Informe de fase 2 Jenkins e integración continua local

La Fase 2 queda implementada y probada mediante ejecuciones reales del job [parcialbigdata-local](http://127.0.0.1:8080/job/parcialbigdata-local/) en Jenkins. El último build, [#6](http://127.0.0.1:8080/job/parcialbigdata-local/6/), terminó en **SUCCESS** y dejó la API desplegada y saludable. No se publicó ningún cambio de esta fase en GitHub ni se implementaron funciones de datos de fases posteriores.

## Integración autorizada y estrategia Git

Antes de integrar el PR #1 se repitieron pytest local (**4 passed**), pytest Docker (**4 passed**) y la verificación completa de infraestructura. Se revisaron 144 versiones de archivos del historial sin detectar credenciales, datasets ni archivos locales prohibidos.

El PR se encontraba cerrado sin integrar. Se reabrió y se integró tras la autorización explícita del equipo, conservando sus commits y la rama remota. Merge: `2ec352a90f7cd37488bf040f6da13a2435a82350`. [PR #1 integrado](https://github.com/DavierGonz/ParcialBigData/pull/1).

`main` local coincide con `origin/main`. La nueva rama **`develop/final-delivery` existe solo localmente**, sin upstream ni PR nuevo. Se comprobó que GitHub conserva únicamente `main` en `2ec352a` y `feat/phase-1-infrastructure` en `8489629`. El próximo push y PR se reservan para la versión final completa, manteniendo revisión y aprobación entre fases.

Commits locales de implementación:

| Commit | Cambio |
|---|---|
| `b41a590` | Pipeline local con imágenes candidatas, barreras de pruebas y recuperación de API |
| `330088f` | JUnit y dependencias fijadas, marcas de éxito antes de promover y verificación de recuperación |
| `003e500` | Verificación de evidencia de fallos, protección del workspace con recuperación pendiente y guía de CI |

El commit de documentación que incorpora este informe se añade después de las pruebas; no cambia el código ejecutado. El código de los builds #3–#6 y la imagen activa corresponden a `003e5002eba720fccc71a189a5cf4083dccd463f`. Los commits mantienen autoría de automatización, sin atribuir contribuciones a integrantes.

## Implementación

El Jenkinsfile ejecuta checkout de un commit local exportado mediante Git bundle, validación de Compose, construcción, pytest en un contenedor aislado, integración MongoDB/Dask/Spark, prueba HTTP de una candidata separada, promoción local de la API y comprobación posterior. Publica informes JUnit y archiva la revisión de origen y evidencias de despliegue o recuperación.

Se utiliza el mismo motor Docker Desktop, con un solo ejecutor Jenkins y concurrencia deshabilitada en el job. La candidata no publica puertos. Las pruebas deben aprobarse antes de tocar la API activa; un error tras la promoción restaura la imagen anterior por su ID y verifica su salud. La recuperación solo se declara completa cuando los comandos y la comprobación HTTP terminan correctamente. Si queda una recuperación pendiente, el siguiente build no puede borrar ese workspace.

La API activa usa `parcialbigdata-api:deployed`, con etiqueta OCI de revisión y la imagen:

`sha256:5be06fba24498c5138bdc2ec9f2b958070a77ce1351fa693371ed4fefa597fb9`

Jenkins conserva autenticación y CSRF. La herramienta local genera un token API en `secrets/jenkins-local-api.json`, excluido de Git y de Docker. La configuración sensible de Compose se guarda en Jenkins Credentials; el archivo `.env.ci` del workspace se elimina al terminar. No se almacena ninguna credencial Kaggle o GitHub en este pipeline local.

Jenkins sigue en 2.568.3 con JDK 21. Se añadió JUnit `1431.vc0d98912a_756` y sus dependencias obligatorias: la imagen fija ahora 72 plugins. Se comprobó mediante la API de Jenkins que JUnit, Pipeline, Git y GitHub están activos. La página autenticada del job responde HTTP 200. No se deshabilitaron controles de seguridad para ejecutar el pipeline.

## Archivos creados o modificados

| Archivos | Propósito |
|---|---|
| `Jenkinsfile` | Etapas reales, informes, control de inestabilidad, fallos locales y limpieza |
| `ci/pipeline.sh` | Construcción, pruebas, integración, promoción, recuperación y limpieza |
| `ci/compose.candidate.yml` | API candidata aislada sin puerto al host |
| `ci/check_services.py` | Verificación real de MongoDB y ambos workers Dask |
| `ci/faults/test_forced_failure.py` | Fallo intencional optativo; fuera de las pruebas ordinarias |
| `scripts/jenkins_local.py` | Credenciales locales, job, bundles, ejecución y verificación de evidencias |
| `scripts/smoke_api.py` | Prueba HTTP real del contrato de salud |
| `docker/api/Dockerfile` | Smoke HTTP y fixture optativo en imagen de pruebas |
| `docker/jenkins/plugins.txt` | JUnit y árbol completo de dependencias fijadas |
| `docker-compose.yml` | Tag estable configurable de la API desplegada |
| `.githooks/pre-push` | Bloqueo preventivo de publicaciones intermedias |
| `.gitignore`, `.dockerignore` | Exclusión de estado temporal `.ci` |
| `README.md`, `docs/git-workflow.md`, `docs/ci-local.md`, `docs/requisitos.md`, este informe | Política vigente, operación CMD y trazabilidad |

Las evidencias locales están en `reports/jenkins/`, ignorado por Git. El token local y la credencial Jenkins no forman parte de los archivos versionados. `Insumos` permanece intacto: el documento mantiene el SHA-256 `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`.

## Resultados reales en Jenkins

| Build | Escenario | Resultado Jenkins | Duración registrada | Verificación |
|---|---|---|---:|---|
| #1 | Primera ejecución | FAILURE | 61,524 s | Pytest pasó, pero faltaba JUnit. Las etapas posteriores se omitieron; se corrigió la imagen Jenkins |
| #2 | Camino normal tras la corrección | SUCCESS | 64,620 s | Cuatro pruebas, integración, candidata y despliegue correctos |
| #3 | Fallo intencional de pytest | FAILURE esperado | 6,897 s | Cuatro casos aprobados y uno fallido; contenedor e imagen de API sin cambios |
| #4 | HTTP 404 de la candidata | FAILURE esperado | 48,134 s | Pytest e integración pasaron; candidata rechazada sin modificar la API activa |
| #5 | HTTP 404 tras la promoción | FAILURE esperado | 64,172 s | Se restauró el mismo ID de imagen anterior; quedó evidencia `rollback.txt` |
| #6 | Ejecución final normal | SUCCESS | 57,344 s | Cuatro pruebas aprobadas; API promovida, saludable y con revisión exacta verificada |

Las duraciones corresponden a infraestructura pequeña, capas Docker disponibles y lecturas sin dataset; no representan tiempos de ETL ni una comparación Dask/Spark.

La herramienta de verificación no acepta solamente un estado FAILURE: exige el commit esperado, XML real de pytest, el fallo intencional correspondiente o HTTP 404, y compara la imagen y el contenedor antes y después. Para el caso de recuperación también exige el artefacto `rollback.txt` y la ausencia de una evidencia de despliegue exitoso.

Comprobaciones adicionales:

- Último pytest local: **4 passed en 0,15 s**; Compose valida correctamente.
- Los ocho servicios están saludables y `OOMKilled=false`.
- `GET /health` devuelve HTTP 200 con el JSON esperado desde Windows.
- No quedaron contenedores temporales de CI ni `.env.ci` en el workspace Jenkins.
- MongoDB conserva cero accidentes; no se descargó ni procesó US Accidents.
- El hook pre-push rechazó una invocación de prueba local. No se ejecutó ningún push de la rama de desarrollo.
- GitHub mantiene cero webhooks configurados, según comprobación de su API.

## Recursos observados

Dos muestras de `docker stats --no-stream`: **1.292,19 MiB (1,262 GiB)** con nueve contenedores, incluida una candidata, y **1.765,74 MiB (1,724 GiB)** durante la ejecución final. Jenkins consumía respectivamente 474,3 y 515,3 MiB, con límite de 1 GiB. Son lecturas puntuales, no máximos históricos; no incluyen todo el coste de Windows, WSL y BuildKit. Una lectura de Windows durante las pruebas mostró aproximadamente 0,99 GiB libres.

Se mantiene el presupuesto de fase 1 para los servicios permanentes, con 256 MiB adicionales para el contenedor de pruebas o la candidata. Las ejecuciones son secuenciales; no se iniciaron cargas grandes ni se modificó la configuración global de memoria de Docker/WSL.

## Alcance pendiente

El pipeline local completo de infraestructura y API está probado. No equivale a validar todavía GitHub → webhook → checkout remoto → despliegue. Esa comprobación se realizará con la entrega final, tal como se solicitó, junto con la URL HTTPS accesible y las credenciales apropiadas del repositorio privado.

La recuperación cubre la API, no migraciones de datos ni cambios incompatibles de infraestructura. Los despliegues recrean contenedores y no garantizan disponibilidad sin interrupción. Los bundles e imágenes de prueba se conservan para trazabilidad; su limpieza futura deberá seleccionar explícitamente recursos del proyecto.

La descarga automatizada de Kaggle, ingesta, muestreo si hace falta, agregaciones, consultas, endpoints de negocio y benchmark siguen pendientes de sus fases. No se avanzó a ellas. Se espera la revisión y aprobación de la Fase 2 antes de iniciar la siguiente.

## Revisión en Windows CMD

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pytest -q
docker compose ps
curl.exe --fail http://127.0.0.1:5000/health
python scripts\jenkins_local.py status 6
python scripts\jenkins_local.py verify 6
git status --short --branch
git log --oneline main..HEAD
```

Las comparaciones antes/después de un build negativo deben verificarse inmediatamente después de ese build: ejecutar de nuevo su `verify` tras un despliegue posterior compara contra el estado actual y puede fallar correctamente. Sus resultados ya comprobados quedan en `reports/jenkins/build-N.json`. Para repetir toda la batería, seguir secuencialmente [ci-local.md](ci-local.md); no publicar la rama.
