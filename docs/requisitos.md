# Trazabilidad de los requisitos del profesor

Fuente leída completa: `Insumos/Trabajo_Big_Data_Geoespacial-1.docx`, incluidas sus ocho secciones y partes OOXML de notas/comentarios. SHA-256 original: `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`. Se extrajo el texto sin modificar ni reexportar el documento. No se generó una copia con formato ni se evaluó su maquetación.

| Requisito | Tratamiento y límite de fase |
|---|---|
| Sistema integrado, contenedores, reproducible en otro equipo | Compose, Dockerfiles, dependencias fijadas, CMD y volúmenes; probar en segundo equipo queda para revisión |
| Kaggle, georreferenciación, al menos 1 GB o 1 millón de registros | Fase 3: API descargó ZIP completo de 684.855.912 bytes, CSV de 3.058.183.727 bytes y 7.728.394 registros |
| Muestra de al menos un millón si hacen falta recursos | BLAKE2b con semilla fija y módulo 7: 1.103.657 documentos limpios únicos, selección independiente del orden |
| Credencial Kaggle en Jenkins, nunca en repositorio | Secret text `parcialbigdata-kaggle`, inyección en etapa de ingesta, archivos locales excluidos de Git y de imágenes |
| MongoDB, GeoJSON, índice 2dsphere | `accidents` contiene 1.103.657 puntos; verificación completa de geometrías, índice y consultas de prueba |
| Spark master y uno o más workers, conector MongoDB | Master y un worker; conector 10.7.0 lee y escribe agregaciones reales sobre 1.103.657 registros |
| Dask scheduler y dos o más workers | Scheduler y dos workers; ambos ejecutaron tareas reales de la ingesta completa |
| Flask y Jenkinsfile versionable | Salud, proximidad, polígono, geoNear y analítica; pytest y Jenkinsfiles locales |
| GitHub, ramas, PR y webhook de integración a principal | PR #1 integrado con autorización. Desarrollo posterior en `develop/final-delivery` local, sin entregas intermedias; webhook reservado para la integración final |
| Lectura particionada Dask, limpieza de coordenadas, GeoJSON, lotes | Fase 3: 182 particiones, ambos workers, lotes de 500 y upserts; cero coordenadas iniciales inválidas en el CSV real; casos inválidos cubiertos en pruebas |
| Spark: agregaciones espaciales y temporales, colecciones nuevas | Fase 4: analytics_grid (23.599), analytics_time (2.660), analytics_hotspots (50), metadatos y publicación idempotente |
| Consultas parametrizadas $near, $geoWithin y $geoNear | Fase 4: tres operadores probados contra MongoDB; validación, máximo 100 resultados y 3 s por consulta |
| API: radio, polígono GeoJSON, resultados Spark | Cuatro rutas de negocio desplegadas y verificadas por HTTP; contrato en api-geoespacial.md |
| Mapa Leaflet opcional | Fuera del alcance actual; no se requiere GIS de escritorio ni ML |
| Pipeline: checkout, build, pytest, levantar, smoke API, despliegue | Fase 2: ejecutado realmente en Jenkins con checkout desde bundle local, integración, candidata y despliegue API. Checkout remoto y webhook pendientes de validación final |
| Fallo de pruebas impide despliegue | Probado en Jenkins: fallos de pytest y candidata no modifican API activa; fallo posterior a promoción restaura la imagen anterior |
| Operación pesada Dask vs Spark, dos configuraciones de workers | Fase 5: grilla 0,1° sobre la misma muestra, 1/2 workers, calentamiento y tres repeticiones por combinación; métricas brutas, igualdad exacta y límites en informe-fase5.md |
| Entregables: repositorio, README, Compose, Jenkinsfile, informe ≤10 páginas | Archivos técnicos de fase 1; informe académico final y URL pendientes. Este material no sustituye el informe final |
| Sustentación: cambio en vivo y despliegue desde GitHub | Pendiente de ensayo end-to-end una vez desarrollado el sistema |
| Explicación individual y aportes reales en historial | Revisión del equipo; no se simulan autoría, commits ni historial |

Los criterios del documento son infraestructura 20 %, ingesta/procesamiento 25 %, modelado/consultas 20 %, API/CD 20 % y análisis/sustentación 15 %. Esta fase no pretende completar los cinco criterios. No se asignan calendarios ni tareas de programación a los supervisores.
