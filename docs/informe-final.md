# Cierre técnico previo a la publicación final

Fecha: 2 de octubre de 2026. Documento preparado **antes del único commit/push final**. La validación posterior del commit privado de GitHub se adjunta al PR final y a los artefactos Jenkins; no se inventa aquí su número ni resultado futuro. El merge de `main` queda sujeto a aprobación expresa.

## Requisitos y entregables

Se releyeron guía original e informes 1–5. [Matriz requisito → código → evidencia](matriz-final.md), [README operativo](../README.md), [informe académico PDF de seis páginas](informe-academico.pdf), [integración CI](ci-final.md), [sustentación](sustentacion.md). El original conserva SHA-256 `9A2B45C494C0B82AA86466457FC128B2CAFD90FD165C3D1C654518E19561D0C6` y no fue modificado.

Se conserva la arquitectura y la muestra productiva de 1.103.657 documentos, sus 23.599 celdas, 2.660 grupos temporales y 50 hotspots. Las fases históricas acreditan descarga, limpieza, consultas y benchmark. La entrega añade checkout privado, pasarela webhook, pruebas finales, reproducción y documentación; no altera el algoritmo medido.

## Jenkins y seguridad

Deploy key SSH de solo lectura limitada al repositorio privado; host GitHub verificado por claves obtenidas en su API HTTPS. Credenciales en Jenkins, respaldos ignorados en `secrets/`. Jobs `parcialbigdata-main`, `parcialbigdata-validation` y `parcialbigdata-ingestion`. El flujo final no usa bundles; los mecanismos históricos se conservan bajo Jenkinsfiles `*-local`.

Cloudflare Quick Tunnel HTTPS saliente → pasarela Flask → únicamente `/github-webhook/` de Jenkins. HMAC-SHA256 en ambos extremos, validación de repositorio/ramas, límite de cuerpo, SQLite persistente para deduplicar. Administración local, sin abrir router. GitHub entregó ping real HTTP 200 (entrega `3846028575689932800`, hook `691031881`); acceso público `/login` y `/scriptText`: 404; webhook sin firma: 403. La URL temporal debe actualizarse tras reiniciar cloudflared. Main tiene filtro/configuración de trigger; el primer merge real no se ejecuta sin aprobación.

Pipeline: checkout → build de pruebas/motores → pytest → integración MongoDB/Dask/Spark → fixtures y analítica Spark → integración API/MongoDB → construcción candidata → pruebas HTTP → promoción → HTTP. Fallos previos impiden promover; fallo posterior restaura imagen previa. El job de ingesta sigue independiente de Flask.

| Comprobación previa a publicación | Resultado real |
|---|---|
| `parcialbigdata-main` #1 | SUCCESS, 5,565 s; checkout SSH privado de main únicamente, sin despliegue |
| `parcialbigdata-validation-local` #1 | FAILURE esperado, 73,588 s; 62 aprobadas + 1 fallo intencional; imagen y contenedor API iguales |
| Mismo job #2 | FAILURE esperado, 99,127 s; 62 unitarias + 2 Spark + 4 API pasaron; fallo HTTP posterior provocó rollback exacto |
| Mismo job #3 | SUCCESS, 95,471 s; 68 pruebas sin fallos/omisiones, candidata y producción HTTP, revisión de imagen comprobada |
| Pytest local final | 76 aprobadas, 2 omitidas en Windows (bloqueo Linux e integración Docker), 2,74 s |
| Dependencias y Compose | `pip check`, `git diff --check` y configuración Compose válidos |

Los tres ensayos completos usan fuentes de trabajo identificadas por `snapshot-sha256-...`, no se presentan como commits ni checkout remoto. Sus evidencias están en `reports/final/parcialbigdata-validation-local/N/`; `verify_final_build.py` compara resultados, XML e imagen. La prueba remota posterior se distingue por su SHA real y causa GitHub push en Jenkins.

## Reproducción limpia en el mismo host

`reports/reproduction/checkout`: clon local independiente (`--no-local`) de develop más superposición **solo de fuentes candidatas permitidas**, registradas por hash. Esto permite probar antes del único commit final. Se creó una `.venv` nueva con requirements, `.env` con contraseñas aleatorias y proyecto Compose **pbd-repro** con volúmenes nuevos y puertos 15000/18080/18081/18787. No se copió `.env`, credenciales MongoDB, caché, dataset ni volúmenes productivos. La credencial Kaggle existente se suministró explícitamente como entrada externa documentada, sin escribirla en logs.

Se detuvieron los servicios productivos mientras se ejecutaba la instalación aislada; luego se restauraron. Se reutilizaron Docker Desktop, capas de imágenes y caché de paquetes del host. **No constituye una prueba física en un segundo computador.** No se descargó de nuevo software innecesariamente ni se borraron datos productivos.

Primera comprobación: 62 pruebas locales, 62 en imagen API, 16 en imagen de ingesta y 2 Spark pasaron; infraestructura completa nueva saludable. Tres pruebas API con fixtures pasaron y la cuarta falló al exigir datos reales todavía ausentes. Se documentó la causa y el helper de fixtures separa esa prueba; después se completó la reproducción **con el dataset real**, sin ocultar el fallo inicial.

| Operación en volúmenes nuevos | Resultado / tiempo real |
|---|---|
| Descarga completa, sin caché | 684.855.912 bytes; 95,388 s |
| CSV | 3.058.183.727 bytes; mismo SHA-256 que Fase 3 |
| Dask ETL | 182 particiones; 7.728.394 leídas, 0 inválidas/ID ausente; 101,346 s |
| Muestra MongoDB | 1.103.657 seleccionadas e insertadas; 0 duplicados; 2dsphere y consultas válidos |
| Operación de ingesta completa | 203,228 s |
| Spark desde MongoDB nuevo | 95,981 s del job, 104,750 s del comando; sin reutilizar analítica |
| Resultados Spark | 23.599 celdas, 24 horas/2.549 fechas/87 meses, 50 hotspots; misma huella/ejecución |
| API/MongoDB final | 4 aprobadas; smoke HTTP real aprobado |

Evidencias: `reports/reproduction/{execution.log,steps.json,source-manifest.json,data-execution.log,data-steps.json,ingestion.json,resources-summary.json}`; informe Spark en el checkout aislado. Los ocho contenedores de reproducción quedan detenidos, volúmenes conservados. Jenkins fresco se comprobó saludable; no se migraron usuarios/jobs ocultos. La configuración remota de Jenkins se prueba separadamente en la instancia principal.

Recursos durante Spark de reproducción: 21 muestras, máximo simultáneo observado **3.558,83 MiB** de sus ocho servicios; MongoDB **759,4 MiB** de 768, driver 500,5, worker Spark 798,9 MiB. Workers Dask retenían memoria de la ingesta pero no ejecutaban un ETL simultáneo. No se amplió ningún límite. No se midió un máximo continuo de Windows ni se garantizan picos entre muestras. La proximidad de MongoDB al límite sigue siendo una limitación del equipo; evitar cargas concurrentes.

## Archivos, informe y Git

Se añaden `webhook/`, Dockerfile/Compose del webhook, pruebas HMAC/filtros/deduplicación, `jenkins_remote.py`, `validate_final.py`, `verify_final_build.py`, helpers de reproducción/auditoría y generador PDF. Se actualizan Jenkinsfile, pipeline y documentación. El informe PDF se genera con ReportLab, seis páginas verificadas y revisión visual de todas las páginas; dependencias opcionales en `requirements/report.txt` dentro de `.venv`.

Rama: `develop/final-delivery`. Se prepara un único commit final, después de pruebas y auditoría, y un único push autorizado; PR final sin merge. Se conserva el historial de commits previos porque sus hashes identifican evidencias de fases aprobadas. No se reescribe `main`, no se fuerza push y no se crean aportes ficticios. No se creó el commit de demostración.

El control de publicación examina archivos de trabajo y todos los blobs de historia disponibles, buscando rutas prohibidas, tamaño excesivo, formatos de tokens/claves y valores de secretos locales. No es una garantía matemática de ausencia de todo secreto desconocido. `.env`, `.venv`, tokens, claves, datos, cachés y evidencias locales siguen excluidos; las métricas pequeñas de `docs/benchmark` son deliberadamente publicables. Repetir `python scripts\audit_delivery.py` y el control staged antes de confirmar.

## Verificación CMD y límites de cierre

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
docker compose -f docker-compose.yml -f ci/compose.webhook.yml ps
python scripts\verify_infra.py
python scripts\smoke_geo.py http://127.0.0.1:5000
python scripts\jenkins_remote.py status --job parcialbigdata-validation --number N
python scripts\verify_final_build.py N --job parcialbigdata-validation
python scripts\audit_delivery.py
docker stats --no-stream
```

Usar el número real de build remoto comunicado en el PR/cierre. Para recrear fixtures aislados, `python scripts\reproduce_clean.py`; para completar datos nuevos, `python scripts\reproduce_data.py`. El primer helper protege un directorio existente para no sobrescribir evidencia; conservarlo o elegir explícitamente otra ubicación antes de un nuevo ensayo.

Pendientes que requieren revisión/intervención: aprobación del PR y merge definitivo; después, comprobar el primer evento real de main y su despliegue. Sustentación preparada pero no ejecutada por los estudiantes. Segundo equipo físico no disponible. Túnel temporal dependiente del host. La conclusión del benchmark permanece limitada a esta grilla, muestra y equipo; no se inventan mediciones nuevas de rendimiento comparativo.
