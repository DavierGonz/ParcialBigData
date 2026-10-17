# Reanudar este equipo sin reprocesar datos

Docker Desktop debe estar abierto y su motor Linux listo. Desde Windows CMD:

```cmd
cd /d D:\Proyects\ParcialBigData
scripts\resume_local.cmd
```

El script inicia los contenedores existentes respetando dependencias y salud, conserva la imagen local Atlasvial y comprueba HTTP/datos. No construye imágenes, no descarga datos y no ejecuta ingesta ni Spark. No usar `scripts\start.cmd` para reanudar esta instalación: ese script construye y puede sustituir la imagen local de Flask. No usar `down -v`, `prune` ni eliminar volúmenes.

El servicio MongoDB de Windows arranca automáticamente y utiliza 27017. Se conserva intacto. **Compose principal** publica MongoDB del proyecto exclusivamente en **127.0.0.1:27018**, también cuando Jenkins recrea el servicio. Los clientes internos siguen usando `mongodb:27017`. MongoDB comparte las redes backend/frontend para permitir el acceso del host; no se publica ninguna dirección de red externa.

El override ignorado `reports/compass/compose.local.yml` queda como compatibilidad sin puertos ni redes adicionales (`services: {mongodb: {}}`). No es necesario para iniciar, desplegar ni usar Compass. No debe añadirse una segunda publicación.

Aplicar solo ese cambio, sin reconstruir imágenes:

```cmd
docker compose up -d --no-deps --no-build --wait mongodb
```

En Compass editar la conexión del proyecto: host `127.0.0.1`, puerto **27018**, autenticación Username/Password, usuario de aplicación existente y Authentication Database `us_accidents` (o el valor ya configurado de MONGO_DATABASE). Conservar la contraseña guardada; no usar el puerto 27017, que pertenece a otra instalación. No pegar secretos en comandos, capturas o URLs compartidas. Acceder solo para inspeccionar, sin editar documentos. No se abre el router ni se publica MongoDB en la red Wi-Fi.

## Apagado y recuperación

`restart: unless-stopped` ya estaba configurado en los servicios. Los contenedores detenidos explícitamente no se reanudan automáticamente por esa política. Iniciarlos individualmente desde Docker Desktop tampoco coordina las dependencias; utilizar el script. La salud de `/health` indica Flask vivo, no disponibilidad de MongoDB; por eso el script exige salud de Compose y consultas reales.

Para detener ordenadamente sin eliminar nada:

```cmd
docker compose -f docker-compose.yml -f ci\compose.webhook.yml stop -t 60
```

Después, abrir Docker Desktop y ejecutar `scripts\resume_local.cmd`. Un reinicio completo de Windows no equivale a una prueba de segundo equipo. No se han modificado servicios, tareas programadas ni preferencias de arranque de Windows. Un HTTP 500 de Docker Desktop debe distinguirse de errores HTTP Flask: esperar motor listo y conservar el mensaje/log si se repite; no reinstalar ni reinicializar.

## Internet y túnel

Atlasvial se abre en localhost y consulta MongoDB local tanto con Wi-Fi como con hotspot. El fondo OpenStreetMap necesita Internet; si falla se mantiene el contorno local, los puntos y consultas. Cambiar de red puede interrumpir temporalmente conexiones externas.

El Quick Tunnel actual solo publica la pasarela del webhook; no la administración Jenkins ni MongoDB. Su dominio temporal cambia al reiniciar el proceso. Opciones antes de modificar GitHub:

- Quick Tunnel: sin cuenta/dominio estable, exige actualizar la URL del webhook tras cambiar. Se conserva secreto HMAC; no automatizar cambios sin autorización.
- Túnel nombrado Cloudflare: hostname estable, requiere cuenta/dominio y credencial de túnel guardada como secreto local. Publicar únicamente la pasarela existente, nunca Jenkins administrativo.
- Mantener Quick Tunnel y usar una actualización explícita del webhook con el helper existente cuando se autorice; implica un paso manual recurrente.

No se han cambiado webhooks ni credenciales en GitHub durante este diagnóstico. El túnel no es requisito para consultas locales de Atlasvial. No ejecutar builds ni pushes para probar el arranque.

## Verificación del 17 de octubre de 2026

- Se reprodujo el conflicto: `MongoDB` de Windows, inicio automático, proceso `mongod.exe` PID 5276, escuchando en 127.0.0.1:27017. Se dejó en funcionamiento, sin cambios del sistema.
- Docker Engine respondió correctamente durante el diagnóstico. No se reprodujo el HTTP 500 de Docker Desktop y no se atribuye una causa no demostrada. Los contenedores detenidos tenían salidas 0/143; el túnel 137 con `OOMKilled=false`, insuficiente para concluir falta de memoria.
- Se recreó solo MongoDB para cambiar la publicación local a 27018, conservando imagen y volúmenes. Flask y los demás servicios conservaron sus contenedores/imágenes.
- Se detuvieron los diez servicios del proyecto con 60 segundos de gracia y se recuperaron con `resume_local.cmd`: nueve con healthcheck saludable; túnel activo y `/ready` HTTP 200. No se reinició físicamente Windows ni el motor Docker durante esta prueba.
- Antes/después: accidents 1.103.657; analytics_grid 23.599; analytics_time 2.660; analytics_hotspots 50; analytics_runs, analytics_state e ingestion_runs una fila cada una. Índice 2dsphere y volúmenes conservados. Autenticación de aplicación desde Windows por 27018 comprobada.
- Jenkins conserva acceso normal, seis jobs y último main #3 SUCCESS. No se lanzaron builds.
- Datos móviles y router Wi-Fi: conexiones confirmadas por el usuario, navegador Chromium nuevo en cada prueba; ocho teselas OpenStreetMap HTTP 200, ocho imágenes cargadas y consulta geoNear HTTP 200 con ocho accidentes reales en cada red.
- HTTP integrado: HTML/recursos, near, geoNear, within, cinco tipos analíticos y validación aprobados. Pytest: 71 aprobadas, 1,14 s. `git diff --check` correcto. Sin commits ni push.
- Lectura puntual de memoria posterior al reinicio: MongoDB 447,1/768 MiB; Flask 42,82/256 MiB; Jenkins 266,7/1024 MiB; Spark master 136,9/1024 MiB y worker 152,9/1536 MiB. Son instantáneas, no máximos. No se aumentaron límites ni se ejecutaron trabajos de datos.

Evidencias locales ignoradas por Git: `reports/startup/` (estado antes/después, cantidades, conectividad y capturas). La comprobación de GitHub detectó que su URL no coincide con el Quick Tunnel vigente; el último HTTP 200 registrado pertenece a una entrega anterior y no demuestra funcionamiento actual. No se envió un evento ni se modificó GitHub.

## Corrección permanente de Compass antes de publicar Atlasvial

Posteriormente se incorporó `127.0.0.1:27018:27017` a `docker-compose.yml` principal, conservando los mismos volúmenes y las redes backend/frontend. El archivo local quedó sin publicaciones adicionales y el script de reanudación dejó de depender de él. No se necesita modificar Jenkinsfile: `ci/pipeline.sh` ya utiliza Compose principal para infraestructura, promoción y rollback; la publicación ahora forma parte de su configuración versionada.

Se validaron las configuraciones principal y combinada con el override: ambas contienen exactamente una publicación, ligada a 127.0.0.1. Se forzó la recreación únicamente de MongoDB con Compose principal, sin build ni override, y se comprobó autenticación de aplicación desde Windows por 27018, cantidades de todas las colecciones e índice 2dsphere. Atlasvial y sus consultas HTTP siguieron operativos. MongoDB de Windows se mantuvo en 27017, sin cambios. Evidencias: `reports/compass-permanent/`.

Esta prueba reproduce la recreación del servicio gestionado por el pipeline, no constituye un build completo de Jenkins. No se ejecutaron ingestas ni analíticas Spark. La revisión posterior del webhook confirmó que GitHub ya apunta al túnel vigente y registra respuesta 200; el build main sigue siendo #3 SUCCESS hasta autorizar publicación.
