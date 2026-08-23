---
name: mongodb
description: >
  Usa la librería ruvic_mongodb_connector para consultar bases de datos
  MongoDB en modo solo lectura - listar colecciones (list_collections),
  leer documentos con filtro (read_documents), contar documentos
  (count_documents) y obtener estadísticas de una colección
  (collection_stats). Úsala cuando el usuario pida consultar, explorar o
  analizar una base de datos MongoDB.
triggers:
- mongodb
- mongo
- nosql
- base de datos
- consultar colección
- documentos
---

# Conector MongoDB (ruvic_mongodb_connector)

Librería Python de solo lectura para MongoDB. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/MongoDB.git#subdirectory=lib`).

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `mongodb` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_MONGODB_HOST` | Host del servidor (o del cluster, si se usa DNS SRV) |
| `RUVIC_MONGODB_USE_SRV` | (opcional) `true` para `mongodb+srv://` — necesario en MongoDB Atlas y la mayoría de proveedores gestionados |
| `RUVIC_MONGODB_PORT` | Puerto (default 27017). Se ignora si `USE_SRV=true` |
| `RUVIC_MONGODB_DATABASE` | Nombre de la base de datos |
| `RUVIC_MONGODB_USERNAME` | Usuario |
| `RUVIC_MONGODB_PASSWORD` | Contraseña |
| `RUVIC_MONGODB_AUTH_SOURCE` | (opcional) base de datos de autenticación, default = la misma base de datos |
| `RUVIC_MONGODB_CONNECT_TIMEOUT` | (opcional) timeout en segundos |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

## Conexión (siempre igual)

```python
from ruvic_mongodb_connector import MongodbClient

client = MongodbClient()  # lee RUVIC_MONGODB_* del entorno automáticamente
```

## Capacidad 1 — Listar colecciones

```python
collections = client.list_collections()
for c in collections:
    print(f"{c['collection']}: ~{c['documents_estimate']} documentos")
```

## Capacidad 2 — Leer documentos con filtro

```python
docs = client.read_documents("clientes", {"ciudad": "Bogota"}, limit=50)
for doc in docs:
    print(doc)  # cada documento es un dict; _id y fechas vienen como texto
```

El `filter` usa la misma sintaxis de `find()` de MongoDB (operadores `$gt`, `$in`, `$regex`, etc.). Pasa `None` o `{}` para traer todos los documentos hasta el límite.

## Capacidad 3 — Contar documentos

```python
total = client.count_documents("clientes")
en_bogota = client.count_documents("clientes", {"ciudad": "Bogota"})
```

Conteo exacto (no estimado), acepta el mismo tipo de filtro que `read_documents`.

## Capacidad 4 — Estadísticas de una colección

```python
stats = client.collection_stats("ventas")
print(f"Documentos: {stats['document_count']}, Tamaño: {stats['total_size']}")
print(f"Índices: {stats['indexes']}")
```

## Manejo de errores

```python
from ruvic_mongodb_connector import (
    MongodbAuthError, MongodbDataError, MongodbNetworkError,
)

try:
    docs = client.read_documents("pedidos")
except MongodbAuthError:
    print("Credenciales inválidas o sin permiso de lectura")
except MongodbNetworkError:
    print("No se pudo alcanzar el servidor — revisa host/puerto/red")
except MongodbDataError as e:
    print(f"Error de datos: {e}")  # ej. la colección no existe
```

## Comportamiento conversacional

### Cuándo pedir aclaración (y cuándo NO)

Pide aclaración únicamente cuando la consulta requiere filtrar por una entidad
específica (ej. un cliente), el usuario no la nombró ni dio nada que la
identifique, y existe más de una posible. En cualquier otro caso, responde
directo — nunca preguntes "de más".

| Situación | ¿Preguntar? |
|---|---|
| El usuario pide una agregación, ranking o promedio ("¿cuál cliente compró más?", "total del mes") | No — arma el filtro/pipeline necesario y responde, sin necesitar que el usuario elija nada |
| El usuario pide documentos de "el cliente" sin decir cuál, y hay varios posibles | Sí — pregunta cuál, mostrando las opciones disponibles si las tienes a mano |
| El usuario nombra la entidad, exacta o aproximada (ej. "empresa cinco" en vez de "Empresa 5") | No — resuélvelo por coincidencia razonable (ej. `$regex` case-insensitive), no pidas que lo repita exacto |
| El usuario nombra una entidad que no existe en los datos | No es ambigüedad — dilo explícito ("Empresa 25 no existe entre los registros") y muestra qué valores sí hay en esa colección; nunca respondas con un total en 0 o cualquier cifra que sugiera que el registro existe pero está vacío |

### Sugerencias de seguimiento

Después de responder, ofrece una sugerencia de seguimiento solo si deja algo
útil sin resolver — no la agregues en cada respuesta, se vuelve ruido. Ejemplo:
si mostraste los documentos de un cliente, puede tener sentido ofrecer
compararlo contra el promedio general; si ya mostraste un ranking completo,
no sugieras nada más, la respuesta ya está completa.

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_MONGODB_*` (el constructor de `MongodbClient` ya lo hace).
2. Nunca imprimas `RUVIC_MONGODB_PASSWORD` en logs ni en la salida.
3. La librería es de SOLO LECTURA: no intentes `insert_one`, `update_one`, `delete_one` ni similares con ella.
4. Usa `limit` razonable en `read_documents` (default 100) para no traer colecciones enteras.
5. Los `_id` (ObjectId) y las fechas (datetime) ya vienen convertidos a texto en los resultados; no necesitas serializarlos manualmente.
