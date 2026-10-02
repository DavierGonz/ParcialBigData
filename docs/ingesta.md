# Operación de la ingesta (Fase 3)

**Actualización de entrega final:** para operación actual usar `python scripts\jenkins_remote.py run --job parcialbigdata-ingestion` y recoger evidencia con `status --job parcialbigdata-ingestion --number N`. Ese job realiza checkout privado real. Los comandos de bundles siguientes documentan la fase histórica y se conservan como diagnóstico; las reglas de datos/caché siguen vigentes.

El job `parcialbigdata-ingestion-local` usa exclusivamente un commit local exportado por Git bundle. No publica código, no hace checkout remoto y no despliega Flask. Las pruebas unitarias y de integración deben pasar antes de iniciar la descarga. El job de infraestructura/API de la fase 2 se conserva separado.

## Credenciales y ejecución en Windows CMD

Guardar una sola vez un token Kaggle en `secrets\kaggle-token.txt` o las credenciales legacy en `secrets\kaggle.json`. Ambos están excluidos de Git y del contexto Docker. Nunca pegar el valor en comandos, documentación o chats. La herramienta crea una credencial **Secret text** de Jenkins con ID `parcialbigdata-kaggle`. Jenkins la inyecta únicamente en la etapa de ingesta; no se incorpora a imágenes ni a informes. Quien controla el motor Docker puede inspeccionar variables de contenedores: usar este entorno solo con administradores de confianza.

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
python -m pip install -r requirements/dev.txt -r requirements/dask.txt
python scripts\jenkins_ingestion.py credential
python -m pytest tests tests_ingestion -q
```

El código debe estar en un commit local limpio de `develop/final-delivery` para exportar la revisión exacta. No hacer push. Ejecutar el job normal (descarga completa y ETL, o uso de caché):

```cmd
python scripts\jenkins_ingestion.py run
```

El comando muestra el número del build. Sustituir `N` por ese número para recoger artefactos y verificar el resultado, la revisión y que Flask conserva contenedor e imagen:

```cmd
python scripts\jenkins_ingestion.py status N
curl.exe --fail http://127.0.0.1:5000/health
docker compose ps
```

Solo pruebas reales sin dataset: `python scripts\jenkins_ingestion.py run --validate-only`.
Repetir la escritura para comprobar upserts: `python scripts\jenkins_ingestion.py run --force-etl`.
Un build normal posterior verifica hashes y el número de documentos sin reprocesar el CSV si la ingesta quedó completa.

## Descarga y caché

Se utiliza la API REST oficial de Kaggle, con token Bearer o autenticación Basic legacy. Se fija la versión 13 de `sobhanmoosavi/us-accidents`. Si cambia la versión anunciada durante una descarga nueva, el proceso exige revisar explícitamente el cambio. La caché conserva ZIP completo, CSV completo y `manifest.json` en el volumen existente `dataset_cache`, directorio `/data/us-accidents-v13`.

El manifiesto registra fuente, versión, fecha de actualización, licencia, fecha de descarga, tamaños, SHA-256 y columnas leídas del CSV real. Los archivos se escriben temporalmente y el manifiesto se publica al finalizar. Se comprueba longitud HTTP, integridad ZIP y hashes al reutilizar. No se reenvía la cabecera de autenticación a la URL de almacenamiento a la que redirige Kaggle. Un bloqueo Linux sobre el volumen impide dos ingestas simultáneas y se libera al morir el proceso.

Fuente y autenticación: [Kaggle API](https://www.kaggle.com/docs/api), [US Accidents](https://www.kaggle.com/datasets/sobhanmoosavi/us-accidents). Conservar atribución a Sobhan Moosavi y la licencia CC BY-NC-SA 4.0 para el uso académico.

## Limpieza, muestra y carga

Dask lee bloques de 16 MiB y admite como máximo dos particiones en vuelo, con los dos workers existentes de 768 MiB por proceso. Cada tarea limpia y escribe directamente a MongoDB; el coordinador recibe únicamente contadores. El contenedor coordinador tiene límite de 512 MiB. No se carga el CSV completo en pandas ni en la memoria del cliente.

Los descartes se contabilizan en categorías mutuamente excluyentes, en este orden:

1. Coordenadas ausentes: nulo, vacío o marcadores `nan`, `null`, `none`, `na`, `n/a`, sin distinguir mayúsculas.
2. Coordenadas no numéricas o no finitas, incluyendo infinito.
3. Latitud fuera de [-90, 90] o longitud fuera de [-180, 180]. Los extremos y el cero son válidos; no se elimina (0,0) arbitrariamente.
4. ID ausente: no permite identidad estable de los upserts.

Se usan `Start_Lat` y `Start_Lng`. Las coordenadas finales opcionales no causan descarte. No se deduce que un punto sea inválido por encontrarse fuera de una caja aproximada de Estados Unidos. Se conserva el resto de las columnas, con coordenadas iniciales numéricas y Severity entera; los tiempos civiles originales y Timezone se conservan sin inventar una zona UTC.

La muestra incluye IDs cuyo BLAKE2b de 64 bits de `us-accidents-academic-v1:<ID>` módulo 7 sea cero. Es reproducible independientemente del orden de ejecución y recorre todo el CSV; no es una selección de los primeros registros. El tamaño exacto se mide y el job falla si quedan menos de un millón de documentos limpios únicos. No se promete un tamaño exacto ni representatividad estadística por estado.

Cada documento conserva `ID`, usa `_id=ID`, añade `location={type:Point, coordinates:[longitud,latitud]}` y la huella de CSV/versión/ETL/muestreo. Se escriben lotes de 500 mediante ReplaceOne con upsert y orden desactivado. La clave primaria evita duplicados al repetir o recuperar una ejecución parcial. Los efectos de tareas reintentadas son idempotentes; sus contadores inserted/matched pueden reflejar el intento final, mientras el conteo MongoDB es la evidencia de documentos únicos.

La colección `ingestion_runs` marca una ingesta como completa solo después de verificar el mínimo, índice 2dsphere, geometrías de todos los documentos de la huella y consultas `$near` y `$geoWithin`. No se publican endpoints ni agregaciones de negocio. Un fallo puede dejar una ingesta parcial, que se completa mediante upserts al repetir. Esta fase no implementa sustitución atómica de snapshots entre versiones ni elimina documentos de otras fuentes/huellas.

## Evidencias y recursos

Jenkins archiva XML de pytest, commit, comprobación de Flask, informe de ingesta y muestras periódicas de `docker stats` durante la ingesta. El informe persistente queda también en `/data/last-ingestion-report.json`. Los informes y datos están excluidos de Git. Los RSS por partición son lecturas puntuales, no máximos; las muestras de Docker tampoco garantizan capturar picos entre intervalos.

Pruebas Docker independientes:

```cmd
docker compose build dask-scheduler
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml build ingestion ingestion-tests
docker compose up -d --no-build --wait dask-scheduler dask-worker-1 dask-worker-2
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion-tests
docker compose -f docker-compose.yml -f ci/compose.ingestion.yml run --rm --no-deps ingestion python -m ingestion.run --verify-only
```

La verificación independiente requiere una caché íntegra existente; no recibe la credencial. Si falta la caché, falla sin descargar. Para detener los servicios conservando volúmenes: `docker compose stop`. Nunca usar `down -v` para una parada normal.
