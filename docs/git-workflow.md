# Gestión de Git y GitHub

Repositorio privado: https://github.com/DavierGonz/ParcialBigData. Se revisaron los repositorios accesibles de la cuenta antes de crearlo; no existía uno correspondiente a este proyecto. La práctica `Tarea3-BigData` es de astronomía y no se modifica.

El PR #1 de `feat/phase-1-infrastructure` fue revisado técnicamente e integrado en `main` tras la autorización explícita del equipo, mediante el merge `2ec352a`. La rama remota se conserva. Los commits registran trabajo real con sus fechas reales; no pretenden reconstruir una cronología de desarrollo anterior.

La estrategia vigente utiliza `develop/final-delivery` exclusivamente de forma local para las fases restantes. Se permiten commits locales; el próximo push y PR se reservan para la entrega completa. Las revisiones y aprobaciones entre fases siguen siendo necesarias. `.githooks/pre-push` bloquea las publicaciones accidentales; no habilitar `FINAL_DELIVERY_PUSH=1` hasta la entrega final aprobada.

La autorización actual permite al asistente gestionar Git, GitHub, commits, push y pull requests. La integración en `main` requiere revisión y aprobación explícita de la fase por el equipo. No hay aprobación implícita por crear o publicar una rama. No se avanza a otras fases, se hace force push, se eliminan ramas remotas ni se sobrescribe trabajo existente sin autorización explícita.

Los commits creados por el asistente usan la identidad local `Codex (AI assistant) <codex@localhost>`. Es una identidad de automatización, no una cuenta GitHub verificada ni un aporte atribuido a un estudiante. La autenticación de transporte utiliza la cuenta disponible `DavierGonz`; autoría y cuenta que publica son conceptos distintos. No se añaden coautores ficticios.

## Comprobación antes de cada commit

El repositorio activa `.githooks/pre-commit` mediante configuración local. El hook usa exclusivamente `.venv` y examina el contenido preparado en el índice, no solo los archivos de trabajo. Rechaza rutas de credenciales, `.env` reales, entornos virtuales, `Insumos`, reportes locales, datasets, archivos mayores de 5 MiB y patrones conocidos de tokens o contraseñas locales. `.env.example` debe contener valores vacíos en sus campos de credenciales.

El detector reduce errores accidentales, pero no sustituye la revisión del diff ni garantiza detectar cualquier secreto. No omitirlo con `--no-verify`.

Después de clonar y preparar `.venv` según el README, habilitar el hook:

```cmd
git config --local core.hooksPath .githooks
```

Antes de un commit:

```cmd
git status --short
git diff --cached --stat
git diff --cached --check
.venv\Scripts\python.exe scripts\check_staged.py
```

Seleccionar archivos explícitamente para el índice. Mantener `.venv`, `.env`, `reports`, `Insumos`, cachés y datasets fuera del repositorio. No guardar tokens en URLs remotas ni en archivos versionados.

## Jenkins

El repositorio es el origen previsto del Jenkinsfile. La Fase 2 usa un job Jenkins real con commits exportados mediante bundles locales, pruebas y despliegue de la API en Docker Desktop. La integración remota y el webhook quedan para la entrega final. Un webhook operativo requerirá una URL HTTPS accesible desde GitHub y credenciales del repositorio privado gestionadas en Jenkins, sin incrustarlas en el código. Véase [ci-local.md](ci-local.md).

Cada cierre de fase informará rama, commits, pull request, sincronización remota y resultado real de la integración continua. La publicación de esta rama no significa que el pipeline completo esté validado.
