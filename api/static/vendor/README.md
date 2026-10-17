# Recursos de terceros

- **Leaflet 1.9.4**: distribución oficial de npm, fijada por versión. Su licencia BSD-2-Clause está en `leaflet/LICENSE`; origen y hash del paquete en `leaflet/SOURCE.json`. JS, CSS, imágenes y source map se sirven localmente, sin CDN en ejecución.
- **Contorno de Estados Unidos** (`../us-outline.geojson`): geometría USA de Natural Earth, `ne_110m_admin_0_countries`, simplificación de 110m. Origen: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson. Los atributos se redujeron al nombre en español. Natural Earth declara sus datos de dominio público: https://www.naturalearthdata.com/about/terms-of-use/. Es una referencia cartográfica de respaldo, no límites para filtrar accidentes.
- **Teselas OpenStreetMap**: el navegador las solicita directamente a `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Se conserva atribución visible y no se precargan ni descargan áreas para uso sin conexión. Política: https://operations.osmfoundation.org/policies/tiles/.

La base cartográfica requiere Internet; el contorno local, marcadores, rectángulos, consultas y gráficos funcionan sin teselas si Flask/MongoDB están disponibles. No se envían accidentes ni credenciales al proveedor cartográfico; el proveedor recibe las coordenadas de las teselas solicitadas por el mapa visible.
