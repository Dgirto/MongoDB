"""Validación local del conector mongodb: ejercita las 4 capacidades.

Uso:
    python validate_local.py

Requiere las variables RUVIC_MONGODB_* exportadas en el entorno, y una
colección "clientes" accesible en la base de datos configurada.
"""

from ruvic_mongodb_connector import MongodbClient, setup_logging

setup_logging("INFO")
client = MongodbClient()

print("== 1. Colecciones ==")
for c in client.list_collections():
    print(f"  {c['collection']} (~{c['documents_estimate']} documentos)")

print("== 2. Documentos de clientes (filtro ciudad=Bogota) ==")
for doc in client.read_documents("clientes", {"ciudad": "Bogota"}, limit=10):
    print(f"  {doc}")

print("== 3. Conteo de documentos ==")
total = client.count_documents("clientes")
bogota = client.count_documents("clientes", {"ciudad": "Bogota"})
print(f"  total={total} en_bogota={bogota}")

print("== 4. Estadisticas ==")
stats = client.collection_stats("clientes")
print(f"  documentos={stats['document_count']} tamano={stats['total_size']}")
print(f"  indices={stats['indexes']}")
