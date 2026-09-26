# Gestión de Git y GitHub

Repositorio privado: https://github.com/DavierGonz/ParcialBigData. Se revisaron los repositorios accesibles de la cuenta antes de crearlo; no existía uno correspondiente a este proyecto. La práctica `Tarea3-BigData` es de astronomía y no se modifica.

`main` comienza con la configuración de control de versiones. La infraestructura ya implementada se presenta en `feat/phase-1-infrastructure`, mediante commits agrupados por componente y un pull request en borrador. Estos commits registran trabajo existente, con sus fechas reales; no pretenden reconstruir una cronología de desarrollo anterior.

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

El repositorio es el origen previsto del Jenkinsfile. La integración completa, los webhooks y sus pruebas también quedan bajo responsabilidad del asistente, respetando la aprobación entre fases. El pipeline actual es el esqueleto de fase 1; no configura todavía despliegues ni webhooks. Un webhook operativo requerirá una URL HTTPS accesible desde GitHub y credenciales del repositorio privado gestionadas en Jenkins, sin incrustarlas en el código.

Cada cierre de fase informará rama, commits, pull request, sincronización remota y resultado real de la integración continua. La publicación de esta rama no significa que el pipeline completo esté validado.
