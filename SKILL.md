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

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_MONGODB_*` (el constructor de `MongodbClient` ya lo hace).
2. Nunca imprimas `RUVIC_MONGODB_PASSWORD` en logs ni en la salida.
3. La librería es de SOLO LECTURA: no intentes `insert_one`, `update_one`, `delete_one` ni similares con ella.
4. Usa `limit` razonable en `read_documents` (default 100) para no traer colecciones enteras.
5. Los `_id` (ObjectId) y las fechas (datetime) ya vienen convertidos a texto en los resultados; no necesitas serializarlos manualmente.
