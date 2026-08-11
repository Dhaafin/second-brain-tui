import uuid
from pathlib import Path

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from src.rag.engine import (
    COLLECTION_NAME,
    get_embedding_model,
    get_qdrant_client,
    init_collection,
)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split long text into segments with overlap."""
    chunks = []
    start = 0
    text_len = len(text)

    if text_len <= chunk_size:
        return [text]

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def delete_file_index(rel_path: str) -> None:
    """Deletes all vector indices associated with a specific file."""
    client = get_qdrant_client()
    init_collection()

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="filename", match=MatchValue(value=rel_path))]
        ),
    )


def delete_directory_index(dir_path: str) -> None:
    """Deletes all vector indices associated with files inside a specific directory."""
    client = get_qdrant_client()
    init_collection()

    prefix = dir_path.rstrip("/") + "/"
    records_to_delete = set()
    offset = None

    while True:
        records, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=["filename"],
            with_vectors=False,
            offset=offset,
        )
        for record in records:
            payload = record.payload
            if payload and "filename" in payload:
                filename = payload["filename"]
                if filename.startswith(prefix) or filename == dir_path:
                    records_to_delete.add(filename)
        if offset is None:
            break

    for filename in records_to_delete:
        delete_file_index(filename)


def index_file(vault_path: str, rel_path: str) -> None:
    """Read the file, split it, create embeddings, and save them to Qdrant."""
    client = get_qdrant_client()
    model = get_embedding_model()
    init_collection()

    delete_file_index(rel_path)

    full_path = Path(vault_path) / rel_path
    if not full_path.exists():
        return

    try:
        text = full_path.read_text(encoding="utf-8", errors="ignore")
        mtime = full_path.stat().st_mtime

        chunks = chunk_text(text)
        if not chunks:
            return

        embeddings = list(model.embed(chunks))

        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = uuid.uuid4().hex

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "filename": rel_path,
                        "text": chunk,
                        "mtime": mtime,
                        "chunks_index": idx,
                    },
                )
            )

        client.upsert(collection_name=COLLECTION_NAME, points=points)
    except OSError:
        pass


def sync_vault_embeddings(vault_path: str) -> None:
    """Synchronize local Markdown files incrementally with the Qdrant database."""
    client = get_qdrant_client()
    init_collection()
    indexed_files = {}
    offset = None

    while True:
        records, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=["filename", "mtime"],
            with_vectors=False,
            offset=offset,
        )
        for record in records:
            payload = record.payload
            if payload and "filename" in payload and "mtime" in payload:
                indexed_files[payload["filename"]] = payload["mtime"]
        if offset is None:
            break
    resolved_vault = Path(vault_path).resolve()
    EXCLUDED_DIRS = {
        ".obsidian",
        ".git",
        ".trash",
        "node_modules",
        ".venv",
        "__pycache__",
    }

    local_files = set()
    for file_path in resolved_vault.rglob("*.md"):
        if any(part in EXCLUDED_DIRS for part in file_path.parts):
            continue
        if file_path.name == "Agent Memory.md":
            continue

        try:
            rel_path = str(file_path.relative_to(resolved_vault)).replace("\\", "/")
            local_files.add(rel_path)

            stat = file_path.stat()

            if (
                rel_path not in indexed_files
                or stat.st_mtime != indexed_files[rel_path]
            ):
                index_file(str(resolved_vault), rel_path)
        except OSError:
            continue
    for filename in list(indexed_files.keys()):
        if filename not in local_files:
            delete_file_index(filename)
