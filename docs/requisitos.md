# Trazabilidad de los requisitos del profesor

Fuente leída completa: `Insumos/Trabajo_Big_Data_Geoespacial-1.docx`, incluidas sus ocho secciones y partes OOXML de notas/comentarios. SHA-256 original: `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`. Se extrajo el texto sin modificar ni reexportar el documento. No se generó una copia con formato ni se evaluó su maquetación.

| Requisito | Tratamiento y límite de fase |
|---|---|
| Sistema integrado, contenedores, reproducible en otro equipo | Compose, Dockerfiles, dependencias fijadas, CMD y volúmenes; probar en segundo equipo queda para revisión |
| Kaggle, georreferenciación, al menos 1 GB o 1 millón de registros | US Accidents confirmado; descarga completa por API queda pendiente, sin descarga en fase 1 |
| Muestra de al menos un millón si hacen falta recursos | Decisión de diseño: muestreo determinista por identificador/semilla y manifiesto, por implementar; no tomar simplemente el primer millón |
| Credencial Kaggle en Jenkins, nunca en repositorio | Jenkins preparado; credencial y job aún no configurados |
| MongoDB, GeoJSON, índice 2dsphere | Colección vacía `accidents`, validación de Point y coordenadas numéricas, índice real; sin registros del dataset |
| Spark master y uno o más workers, conector MongoDB | Master y un worker, conector incorporado en imagen y smoke de lectura sin agregaciones |
| Dask scheduler y dos o más workers | Scheduler y dos workers; prueba pequeña ejecutada en cada worker |
| Flask y Jenkinsfile versionable | GET /health, pytest y Jenkinsfile inicial; archivo preparado para que el equipo lo versione |
| GitHub, ramas, PR y webhook de integración a principal | PR #1 integrado con autorización. Desarrollo posterior en `develop/final-delivery` local, sin entregas intermedias; webhook reservado para la integración final |
| Lectura particionada Dask, limpieza de coordenadas, GeoJSON, lotes | Pendiente; se documentarán reglas y cantidades de descartes con los datos reales |
| Spark: agregaciones espaciales y temporales, colecciones nuevas | Pendiente; nombres/modelos finales se definirán al desarrollar esa fase |
| Consultas parametrizadas $near, $geoWithin y $geoNear | Pendiente explícito; el índice preparado no equivale a implementar consultas |
| API: radio, polígono GeoJSON, resultados Spark | Pendiente; no se presentan endpoints ficticios |
| Mapa Leaflet opcional | Fuera del alcance actual; no se requiere GIS de escritorio ni ML |
| Pipeline: checkout, build, pytest, levantar, smoke API, despliegue | Fase 2: ejecutado realmente en Jenkins con checkout desde bundle local, integración, candidata y despliegue API. Checkout remoto y webhook pendientes de validación final |
| Fallo de pruebas impide despliegue | Probado en Jenkins: fallos de pytest y candidata no modifican API activa; fallo posterior a promoción restaura la imagen anterior |
| Operación pesada Dask vs Spark, dos configuraciones de workers | Pendiente; tiempos y memoria deberán medirse, no extrapolar resultados de los smoke tests |
| Entregables: repositorio, README, Compose, Jenkinsfile, informe ≤10 páginas | Archivos técnicos de fase 1; informe académico final y URL pendientes. Este material no sustituye el informe final |
| Sustentación: cambio en vivo y despliegue desde GitHub | Pendiente de ensayo end-to-end una vez desarrollado el sistema |
| Explicación individual y aportes reales en historial | Revisión del equipo; no se simulan autoría, commits ni historial |

Los criterios del documento son infraestructura 20 %, ingesta/procesamiento 25 %, modelado/consultas 20 %, API/CD 20 % y análisis/sustentación 15 %. Esta fase no pretende completar los cinco criterios. No se asignan calendarios ni tareas de programación a los supervisores.
