# Jenkins e integración continua local

La Fase 2 ejecuta el Jenkinsfile real en el contenedor Jenkins. El origen de código es un commit local exportado mediante `git bundle`; no requiere ni realiza push a GitHub. El webhook y la prueba desde el repositorio remoto se reservan para la integración final. No se descarga Kaggle ni se ejecuta ETL en esta fase.

## Flujo verificado por el job

1. Checkout de un commit exacto desde `/var/jenkins_home/local-sources/<commit>.bundle`, con comprobación de su SHA. El Jenkinsfile configurado en el job procede de ese mismo commit.
2. Validación silenciosa de Compose utilizando una credencial Jenkins; no imprime contraseñas.
3. Construcción de imágenes de pruebas, candidata y componentes de datos. Jenkins no se reconstruye a sí mismo dentro de un job.
4. Pytest dentro de un contenedor sin red. Se publica su XML mediante JUnit; un error o resultado inestable impide continuar.
5. Arranque de MongoDB, Dask y Spark; comprobación de autenticación, esquema e índice, trabajo en ambos workers Dask y lectura con el conector de Spark.
6. Arranque de la candidata en otro proyecto Compose, sin puertos al host, y prueba HTTP real de `/health`.
7. Promoción local de la API al tag `parcialbigdata-api:deployed`, espera de salud y nueva prueba HTTP. Si falla, se restaura el ID de imagen capturado antes de la promoción y se verifica de nuevo la API anterior.
8. Limpieza del contenedor de pruebas, candidata y red temporal; archivo de evidencias. Los volúmenes de datos y Jenkins se conservan.

El despliegue actual solo promueve la API. Las imágenes de infraestructura se levantan tras pasar pytest, pero no tienen rollback transaccional: este laboratorio no pretende resolver migraciones de bases de datos o cambios incompatibles de motores. El pipeline completo de datos se ampliará cuando esas fases estén aprobadas e implementadas.

La promoción exige marcas de éxito de pytest, integración y candidata dentro del workspace limpio. `disableConcurrentBuilds`, un solo ejecutor y el agente reservado durante el pipeline evitan dos ejecuciones simultáneas del job. No ejecutar `scripts\start.cmd`, reconstrucciones o cambios manuales de la API mientras un job esté desplegando.

## Preparar desde Windows CMD

Primero seguir el README para crear `.venv`, instalar dependencias, generar `.env` y levantar la infraestructura. El Jenkins final de esta fase incluye JUnit y 72 plugins/dependencias fijados. Si la infraestructura procede de la fase anterior:

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
docker compose build jenkins
docker compose up -d --no-deps --no-build --wait --wait-timeout 180 jenkins
python scripts\jenkins_local.py setup
```

`setup` se autentica con el administrador inicial si todavía no existe una credencial local. Genera un token API y lo guarda exclusivamente en `secrets/jenkins-local-api.json`, ignorado por Git y Docker. Conserva la autenticación de Jenkins, su asistente y las cuentas existentes; no crea usuarios de estudiantes ni desactiva CSRF. La configuración `.env` se guarda cifrada por Jenkins como credencial de tipo texto `parcialbigdata-compose-env`. No se configura una credencial GitHub ni Kaggle durante esta fase.

Si ya se reemplazó el administrador inicial, crear un token desde la cuenta administradora elegida y preparar privadamente `secrets/jenkins-local-api.json` con las claves `username`, `token` y `url`. No compartir ese archivo ni pegar el token en la conversación. El script no reemplaza jobs o credenciales ajenos: solo administra los identificados con su marcador de proyecto.

El job local opera exclusivamente sobre el proyecto Compose `parcialbigdata`. Mantener ese nombre y el puerto Jenkins 8080 en la configuración predeterminada; si se cambia el puerto, ajustar el campo `url` de la credencial local. La plantilla no requiere instalar paquetes Python adicionales fuera de `.venv`; la herramienta usa la biblioteca estándar.

## Ejecutar código local sin publicarlo

El árbol de trabajo debe estar limpio. Los commits locales están permitidos; el asistente los prepara tras revisar el índice. Para exportar y ejecutar el commit actual:

```cmd
python scripts\jenkins_local.py run
```

El comando prepara el job y devuelve un número de build. Para consultar o verificar, sustituir `NUMERO` por ese número real:

```cmd
python scripts\jenkins_local.py status NUMERO
python scripts\jenkins_local.py verify NUMERO
```

`verify` debe ejecutarse cuando el build haya terminado. Comprueba su resultado, la revisión exacta, el XML de pruebas y el estado real de la imagen desplegada. Un build todavía activo no cuenta como verificado. El job se puede revisar en http://127.0.0.1:8080/job/parcialbigdata-local/ con autenticación.

`reports/jenkins/` conserva los bundles, metadatos antes/después, consola redactada y artefactos descargados; está excluido del repositorio. Los bundles contienen únicamente la historia Git versionada, nunca archivos locales ignorados. El job conserva quince ejecuciones en Jenkins; los bundles locales y tags de imágenes no se eliminan automáticamente, para conservar evidencia y posibilidades de recuperación.

## Pruebas negativas controladas

Ejecutarlas secuencialmente y verificar cada número antes de iniciar la siguiente:

```cmd
python scripts\jenkins_local.py run --fault pytest
python scripts\jenkins_local.py verify NUMERO
python scripts\jenkins_local.py run --fault candidate-smoke
python scripts\jenkins_local.py verify NUMERO
python scripts\jenkins_local.py run --fault post-deploy
python scripts\jenkins_local.py verify NUMERO
```

Estos builds deben terminar en **FAILURE**. `verify` confirma que fallaron por el motivo esperado y que respetaron el estado de despliegue:

- `pytest`: incluye explícitamente un único test fallido de `ci/faults`, excluido de las pruebas ordinarias. La API conserva su contenedor e imagen.
- `candidate-smoke`: solicita una ruta inexistente de la candidata y obtiene HTTP 404. La API desplegada conserva su contenedor e imagen.
- `post-deploy`: fuerza HTTP 404 después de promover la candidata. Se recupera el mismo ID de imagen anterior; el contenedor cambia porque se recrea durante la recuperación.

La inyección está prohibida en modo `SCM`. El Jenkinsfile no silencia los errores con `catchError` ni despliega desde una condición `post always`; el bloque final solo recupera si hay una promoción incompleta, limpia y archiva evidencia.

Si la recuperación también falla, el build permanece fallido y conserva `.ci/deployment.pending` y `.ci/previous-image` en su workspace para diagnóstico. No iniciar otro build que limpie ese workspace antes de resolver la API. Los despliegues recrean el contenedor; no se promete disponibilidad sin interrupciones ni rollback de datos.

## Integración final pendiente

En la entrega final se publicará la rama completa, se preparará el PR final y se configurará un job desde SCM con credenciales restringidas para el repositorio privado. Entonces se verificarán GitHub → webhook HTTPS → Jenkins → checkout → pruebas → despliegue. No hay un webhook configurado ahora y no se ha expuesto Jenkins a Internet. Las pruebas locales no sustituyen esa validación final.

Referencias: [API remota de Jenkins](https://www.jenkins.io/doc/book/using/remote-access-api/), [publicación de pruebas y omisión de despliegue cuando hay inestabilidad](https://www.jenkins.io/doc/pipeline/tour/tests-and-artifacts/) y [sintaxis declarativa](https://www.jenkins.io/doc/book/pipeline/syntax/).
