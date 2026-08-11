from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

_qdrant_client = None
_embed_model = None
COLLECTION_NAME = "notes"
DB_FILE = ".qdrant_notes.db"


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(path=DB_FILE)
    return _qdrant_client


def get_embedding_model() -> TextEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embed_model


def init_collection() -> None:
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def query_semantic_notes(query_text: str, limit: int = 5) -> list:
    client = get_qdrant_client()
    model = get_embedding_model()

    init_collection()

    query_vector = next(iter(model.embed([query_text]))).tolist()

    response = client.query_points(
        collection_name=COLLECTION_NAME, query=query_vector, limit=limit
    )

    return response.points
