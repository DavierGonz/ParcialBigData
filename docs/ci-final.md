# Integración GitHub–Jenkins

El flujo final usa `CpsScmFlowDefinition` con GitSCM, URL SSH privada, deploy key de solo lectura y claves de host obtenidas desde la API HTTPS de GitHub. No consume bundles. `scripts/jenkins_remote.py setup` configura los jobs y credenciales; es idempotente y rechaza sustituir jobs/credenciales no administrados por el proyecto. El README contiene el orden desde una instalación vacía.

## Transporte y seguridad

GitHub → HTTPS Cloudflare Quick Tunnel → `webhook:8090` → `jenkins:8080/github-webhook/`. No se publica ningún puerto adicional Windows ni se abre el router. El túnel solo alcanza la pasarela; la aplicación no ofrece un proxy genérico.

La pasarela limita cuerpo a 512 KiB, exige HMAC-SHA256 del cuerpo original, repositorio exacto, ID de entrega y SHA válidos. Admite `ping` y push de `refs/heads/main`/`refs/heads/develop/final-delivery`; otros eventos/ramas se ignoran. SQLite persiste entregas satisfactorias durante 30 días. Repeticiones no vuelven a disparar Jenkins; errores de reenvío devuelven 502 y permiten reentrega. Jenkins verifica también el mismo secreto en el plugin GitHub. Un solo proceso Gunicorn con dos hilos comparte el estado persistente.

`setup-webhook` registra evento push, JSON, TLS verificado y el secreto de `secrets/webhook-secret.txt`. El endpoint público `/health` revela únicamente salud de la pasarela. `/login` y `/scriptText` responden 404; un webhook sin firma responde 403. Las firmas no se imprimen ni se versionan.

Cloudflared 2026.9.3 fijado por digest; pasarela y túnel con 128 MiB/0,25 CPU cada uno. Quick Tunnel proporciona una URL temporal: al reiniciar cloudflared, ejecutar `setup-webhook` nuevamente. No es una solución de disponibilidad permanente; depende del Windows encendido y del servicio externo. Para uso continuo, migrar a túnel nombrado y dominio administrado por el equipo. No se inventa una cuenta o dominio disponible.

Fuentes: [validar firmas GitHub](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries), [Quick Tunnels y limitaciones](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [plugin GitHub Jenkins](https://plugins.jenkins.io/github/), [GitSCM](https://plugins.jenkins.io/git/).

## Jobs y barreras

`parcialbigdata-main` sigue main; `parcialbigdata-validation` sigue develop. El evento GitHub solicita sondeo SCM; el filtro de rama y el cambio de revisión determinan qué job se ejecuta. Main tiene un checkout inicial de solo lectura para establecer su referencia antes de la primera entrega de develop. Ese build no se presenta como despliegue completo.

Secuencia real del Jenkinsfile: checkout → validar configuración → construir imágenes de pruebas/motores → pytest → MongoDB/Dask/Spark → fixture Spark y analítica real → API/MongoDB → construir candidata → pruebas HTTP de candidata → promocionar → HTTP de producción. Marcas por etapa exigen todas las barreras. Se archivan JUnit, revisión, analítica e identidad de imagen desplegada. El job de ingesta ejecuta sus propias pruebas antes de Kaggle y no modifica Flask.

La analítica reutiliza resultados completos de la misma muestra después de comprobar totales. No se incluye el benchmark pesado en CI. Un ejecutor evita dos pipelines simultáneos; las operaciones manuales también deben respetar la exclusión de cargas.

Pruebas negativas, únicamente en el job de validación autenticado, con datos previamente cargados:

```cmd
python scripts\jenkins_remote.py run --job parcialbigdata-validation --fault pytest
python scripts\verify_final_build.py N --job parcialbigdata-validation
python scripts\jenkins_remote.py run --job parcialbigdata-validation --fault post-deploy
python scripts\verify_final_build.py M --job parcialbigdata-validation
```

Esperar cada build antes del siguiente. `pytest` debe fallar y dejar contenedor/imagen intactos. `post-deploy` provoca HTTP 404 después de promover y debe terminar FAILURE con `rollback.txt`, sin `deployment.txt`, restaurando exactamente la imagen previa. No ejecutar esos fallos durante una demostración normal.

## Recuperación

Antes de promocionar se guarda el ID de la imagen previa y `.ci/deployment.pending`. Un fallo restaura etiqueta, recrea únicamente API y exige `/health`. Si no puede recuperarse, conserva marcador/workspace y bloquea otro checkout.

No borrar el workspace. Revisar la consola del build y resolver primero Docker, red o credenciales. En el mismo job, un administrador puede reanudar una etapa de recuperación con la credencial `parcialbigdata-compose-env`, escribiéndola a `.env.ci` con permisos privados, y ejecutar `bash ci/pipeline.sh cleanup` en el workspace original con los mismos `JOB_BASE_NAME`/`BUILD_NUMBER`. El helper `rollback` solo actúa si existe el marcador; conserva la imagen previa. Verificar HTTP e imagen antes de retirar manualmente cualquier marcador. Si la imagen previa se eliminó fuera del pipeline, recuperar una imagen conocida de sus artefactos antes de reanudar; no afirmar rollback satisfactorio sin esa comprobación.

## Evidencias y revisión final

Las pruebas previas al único commit usan `validate_final.py`: archivo tar de fuentes permitidas identificado por SHA-256, sin `.git`, secretos ni datos. Su etiqueta `snapshot-sha256-...` las distingue de un checkout Git. El pipeline remoto posterior usa el commit real y el mismo Jenkinsfile. `verify_final_build.py` verifica XML, imagen/revisión y estados de rollback; guarda evidencia en `reports/final/`, excluido del repositorio.

La entrega final registra el evento GitHub y build remoto en el PR y cierre de revisión. Un evento real de merge a main solo puede comprobarse después de su aprobación; no se sustituye por una afirmación anticipada. No se integra automáticamente el PR.
