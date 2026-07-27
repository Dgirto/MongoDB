# Conector MongoDB (CON-020)

Conector Ruvic de solo lectura para MongoDB. Permite listar colecciones,
leer documentos con filtro, contar documentos y obtener estadísticas de
una colección.

## Instalación

```bash
pip install git+https://github.com/Dgirto/MongoDB.git#subdirectory=lib
```

Python 3.10+. Dependencia única: `pymongo>=4.6,<5.0`.

## Permisos requeridos en el servidor

Crea un usuario dedicado de solo lectura (no reutilizar un usuario admin o
de aplicación):

```javascript
use produccion
db.createUser({
  user: "ruvic_reader",
  pwd: "CAMBIA_ESTA_CONTRASEÑA",
  roles: [{ role: "read", db: "produccion" }]
})
```

- Rol `read` sobre la base de datos a exponer: necesario para
  `db.list_collections`, `db.read`, `db.count` y `db.stats`.
- No se otorgan roles de escritura (`readWrite`) ni de administración
  (`dbAdmin`, `userAdmin`, etc.).
- Si tu servidor tiene `authSource` distinto a la base de datos consultada
  (usuarios creados en `admin`, común en MongoDB Atlas), indícalo en el
  campo "Base de datos de autenticación" del formulario.

## MongoDB Atlas y otros proveedores gestionados

Atlas (y la mayoría de proveedores gestionados) no exponen el cluster en un
host:puerto directo — requieren el esquema `mongodb+srv://`, que resuelve
los nodos reales vía DNS SRV. Para conectarte a Atlas:

- Activá **`RUVIC_MONGODB_USE_SRV=true`** (campo "Usar DNS SRV" en el
  formulario). El campo `PORT` se ignora en ese modo.
- `HOST` es el hostname del cluster tal como lo muestra Atlas en "Connect"
  (ej. `cluster0.abcde.mongodb.net`), **sin** `mongodb+srv://` ni
  credenciales en la URL.
- `AUTH_SOURCE` normalmente debe ser **`admin`** en Atlas (los usuarios de
  base de datos se autentican contra `admin`, no contra la base que vas a
  consultar).

## Variables de entorno (`RUVIC_MONGODB_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_MONGODB_HOST` | Sí | Host del servidor (o del cluster, si `USE_SRV=true`) |
| `RUVIC_MONGODB_USE_SRV` | No (default `false`) | `true` para `mongodb+srv://` (Atlas y proveedores gestionados) |
| `RUVIC_MONGODB_PORT` | No (default `27017`) | Puerto. Se ignora si `USE_SRV=true` |
| `RUVIC_MONGODB_DATABASE` | Sí | Base de datos a consultar |
| `RUVIC_MONGODB_USERNAME` | Sí | Usuario |
| `RUVIC_MONGODB_PASSWORD` | Sí | Contraseña |
| `RUVIC_MONGODB_AUTH_SOURCE` | No (default: la misma base de datos) | Base de datos de autenticación (usar `admin` en Atlas) |
| `RUVIC_MONGODB_CONNECT_TIMEOUT` | No (default `10`) | Timeout de conexión en segundos |

## Pruebas locales

Con Docker:

```bash
docker run -d --name mongo-test \
  -e MONGO_INITDB_ROOT_USERNAME=root \
  -e MONGO_INITDB_ROOT_PASSWORD=root123 \
  -e MONGO_INITDB_DATABASE=demo \
  -p 27017:27017 \
  mongo:7

docker exec -i mongo-test mongosh -u root -p root123 --authenticationDatabase admin demo <<'JS'
db.clientes.insertMany([
  { nombre: "ACME", ciudad: "Bogota" },
  { nombre: "Globex", ciudad: "Medellin" },
]);
db.createUser({
  user: "ruvic_reader",
  pwd: "reader123",
  roles: [{ role: "read", db: "demo" }],
});
JS
```

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_MONGODB_HOST=localhost
export RUVIC_MONGODB_PORT=27017
export RUVIC_MONGODB_DATABASE=demo
export RUVIC_MONGODB_USERNAME=ruvic_reader
export RUVIC_MONGODB_PASSWORD=reader123

python test_connection.py
python validate_local.py
```

Prueba también los casos de error (contraseña incorrecta, host inalcanzable,
colección inexistente) y verifica que los mensajes sean claros.

## Notas de integración

- El conector nunca invoca operaciones de escritura (`insert`, `update`,
  `delete`): solo emite comandos de lectura (`find`, `count_documents`,
  `collStats`). Segunda barrera: el usuario de MongoDB solo debe tener el
  rol `read`.
- `read_documents` y `count_documents` aceptan un `filter` con la misma
  sintaxis de `find()` de MongoDB (operadores `$gt`, `$in`, `$regex`, etc.).
- Los tipos BSON no serializables (`ObjectId`, `datetime`) se convierten a
  texto automáticamente en las respuestas.
- `list_collections` usa `estimated_document_count()` (rápido, basado en
  metadata); `count_documents` hace un conteo exacto sobre el filtro dado.
