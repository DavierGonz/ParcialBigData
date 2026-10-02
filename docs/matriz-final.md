# Matriz de requisitos y evidencia

Fuente: guía original `Insumos/Trabajo_Big_Data_Geoespacial-1.docx`, secciones 1–8, releída antes de publicar. SHA-256 `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6`. Los informes históricos se conservan y sus pendientes se interpretan según la fase en que fueron escritos.

| Requisito de la guía | Implementación | Prueba o evidencia real | Estado antes de publicación final |
|---|---|---|---|
| Sistema integrado y Docker Compose | `docker-compose.yml`, seis imágenes propias y redes/volúmenes | Fase 1: arranque, reinicio y conectividad de ocho servicios | Verificado en mismo host |
| Dataset Kaggle georreferenciado ≥1 GB o ≥1 millón | US Accidents v13, CSV 3.058.183.727 bytes | Fase 3: descarga real API, hashes y manifiesto | Verificado |
| Descarga automática desde pipeline, token en Jenkins | `ingestion/download.py`, job de ingesta, credencial `parcialbigdata-kaggle` | Fase 3 build #1: descarga y carga sin intervención; repeticiones sin descarga | Verificado; checkout remoto del job pendiente de cierre |
| Muestra permitida ≥1 millón | BLAKE2b, semilla fija y módulo 7 | 1.103.657 documentos únicos en las fases 3–5 | Verificado |
| MongoDB, documentos GeoJSON, índice 2dsphere | `docker/mongo/init.js`, `ingestion`, colección accidents | Validación completa e índice; pruebas reales de proximidad e inclusión | Verificado |
| Spark master y ≥1 worker, conector MongoDB | Spark 3.5.8, conector 10.7.0 | Lectura y escritura reales de agregados, pruebas de fixture | Verificado |
| Dask scheduler y ≥2 workers | Servicios Dask, ETL particionado | Fase 3: 182 particiones, ambos workers ejecutaron tareas | Verificado |
| Lectura, limpieza y carga por lotes | Coordenadas iniciales válidas, GeoJSON lon/lat, upserts de 500 | 7.728.394 leídos, 0 descartes de coordenadas reales; fixtures inválidos y repetición sin duplicados | Verificado |
| Spark espacial, temporal y concentraciones, nuevas colecciones | Grilla 0,1°, horas/fechas/meses, 50 hotspots | 23.599 celdas, 2.660 grupos temporales; cada granularidad suma 1.103.657 | Verificado |
| Consultas parametrizadas near, geoWithin y geoNear | `api/repository.py`, `api/validation.py` | Fixtures MongoDB y smoke HTTP; límites y validaciones | Verificado |
| API radio, polígono y resultados Spark | Cuatro endpoints de negocio más salud | Fase 4 Jenkins #8: 51 pruebas; Fase 5 regresión Docker y HTTP | Verificado |
| Jenkinsfile: checkout, build, pytest, integración, levantar, smoke y despliegue | `Jenkinsfile`, `ci/pipeline.sh`, candidata aislada | Fases 2/4 ejecutadas con bundles locales | Checkout real y build remoto pendientes de cierre |
| Fallo de pruebas impide despliegue | Barreras y rollback de API | Validación final snapshot #1: pytest bloqueó despliegue; #2: rollback exacto; #3: SUCCESS con 68 pruebas | Verificado nuevamente |
| GitHub, ramas, PR, webhook al integrar en main | Repositorio privado y rama develop/final-delivery; PR #1 integrado | Historial y PR existentes | Webhook HTTPS y PR final pendientes; merge final requiere aprobación |
| Benchmark dos configuraciones por motor | `benchmark/`, 1/2 workers, entrada idéntica | Fase 5: 4 calentamientos + 12 mediciones; igualdad exacta de celdas | Verificado; límites de interpretación en informe |
| README, repositorio, Compose, Jenkinsfile e informe ≤10 páginas | README final, `scripts/build_report.py`, PDF académico | PDF de seis páginas revisadas visualmente; guía CMD y código reproducible | Verificado antes de publicar |
| Reproducible en otro equipo | Imágenes/dependencias fijadas, configuración explícita | Nuevo checkout/venv/contraseñas/volúmenes; descarga completa, 1.103.657 documentos, Spark y API pasaron | Verificado en entorno limpio del mismo host; segundo equipo físico no disponible |
| Sustentación cambio → publicación → despliegue, explicación individual | `docs/sustentacion.md`, ejemplo /demo y prueba | Procedimiento preparado, sin crear commit ni atribuir ensayo a estudiantes | Ejercicio listo; ejecución en sustentación pendiente |
| Mapa Leaflet opcional | No implementado | No es requisito obligatorio | Fuera de alcance |

La validación sobre `main` después de integrar el PR no puede afirmarse antes de la aprobación del merge. Se distinguirán el evento real de GitHub sobre la rama de entrega, la validación del filtro de `main` y el primer despliegue posterior al merge.

## Evidencia de cierre previa al único push

La configuración SCM privada se comprobó con checkout SSH real de main (build de solo lectura #1). El pipeline completo se probó antes del commit mediante snapshot identificado: `parcialbigdata-validation-local` #3, SUCCESS, 95,471 s y 68 pruebas. El webhook recibió ping real de GitHub HTTP 200; pasarela HMAC, rutas administrativas 404 y petición sin firma 403 comprobadas. La fila de publicación remota se completa con el build del commit publicado y su entrega GitHub en el **PR final**, porque solo pueden existir después del único push autorizado. No se confunden esas evidencias con las de snapshots.

La reproducción completa independiente obtuvo el mismo hash del CSV, 1.103.657 documentos, 23.599 celdas y todas las granularidades coherentes. Detalles, fallos de diagnóstico y recursos en [informe-final.md](informe-final.md). Los informes 1–5 no se reescriben: son evidencia histórica.
