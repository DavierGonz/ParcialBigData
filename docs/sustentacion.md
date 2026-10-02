# Ejercicio de sustentación: cambio pequeño hasta HTTP

Procedimiento preparado; **no se ha creado el endpoint ni el commit de demostración**. Realizar después de aprobar/integrar la entrega final. Explicar individualmente el código que cada integrante comprenda, sin atribuir contribuciones ficticias ni dividir tareas de programación.

## Preparación

Confirmar Docker saludable, muestra y agregados publicados, jobs sin ejecutar, webhook con entrega reciente HTTP 200 y `main` sincronizada. Si el túnel reinició, actualizarlo mediante `python scripts\jenkins_remote.py setup-webhook`. Tener acceso al repositorio privado y Jenkins local; no mostrar secretos ni la configuración completa de Docker en pantalla.

## Cambio propuesto

Crear un endpoint informativo `GET /demo` que devuelva `{"dataset":"US Accidents","grid_degrees":0.1}`. En la factoría `create_app` de `api/__init__.py`, añadir antes de devolver `app`:

```python
    @app.get('/demo')
    def demo():
        return {'dataset': 'US Accidents', 'grid_degrees': 0.1}
```

Añadir `tests/test_demo.py`:

```python
from api import create_app


def test_demo():
    response = create_app({'TESTING': True}).test_client().get('/demo')
    assert response.status_code == 200
    assert response.json == {'dataset': 'US Accidents', 'grid_degrees': 0.1}
```

## Flujo en Windows CMD

Estos comandos pertenecen al ensayo futuro; no ejecutarlos como parte de la entrega actual:

```cmd
cd /d D:\Proyects\ParcialBigData
call .venv\Scripts\activate.bat
git switch main
git pull --ff-only origin main
git switch -c demo/endpoint
```

Editar los dos archivos, ejecutar pruebas y revisar diff. Un fallo debe corregirse antes del commit:

```cmd
python -m pytest tests -q
git diff --check
git diff
git add api/__init__.py tests/test_demo.py
python scripts\check_staged.py
git commit -m "feat(demo): expose dataset information endpoint"
set FINAL_DELIVERY_PUSH=1
git push -u origin demo/endpoint
set FINAL_DELIVERY_PUSH=
gh pr create --base main --head demo/endpoint --title "Demo: dataset information endpoint" --body "Adds GET /demo and its HTTP contract test."
```

Revisar PR y aprobar el merge explícitamente. La rama demo no dispara el despliegue: el push/merge de **main** es el evento que debe iniciar `parcialbigdata-main`. Integrar desde GitHub tras esa revisión, sin force push. Mostrar Recent deliveries del webhook (HTTP 200), causa GitHub push, checkout del SHA de main y las etapas sucesivas de Jenkins.

Antes de desplegar `/demo` debe responder 404. Después de `SUCCESS`:

```cmd
curl.exe --fail http://127.0.0.1:5000/demo
curl.exe --fail http://127.0.0.1:5000/health
python scripts\verify_final_build.py N --job parcialbigdata-main
```

Comprobar respuesta exacta y revisión OCI igual al commit desplegado. Si no llega el evento, revisar URL temporal, entrega/firma y sondeo SCM; no sustituir silenciosamente el webhook por un build manual. Una construcción manual puede diagnosticar, pero debe identificarse como tal.

Para explicar la arquitectura, seguir un accidente desde el ID original hasta GeoJSON `[lon, lat]`, mostrar `2dsphere`, ejecutar `$geoNear`, consultar un hotspot y comparar las medianas publicadas. Aclarar que frecuencia no significa riesgo, grilla angular no tiene área constante y el benchmark solo cubre esta operación/dataset/equipo.
