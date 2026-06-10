"""Cliente Qdrant para RAG semántico de objeciones.

Usa fastembed (local) con un modelo multilingüe — sin API key de embeddings.
"""

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

COLLECTION = "objeciones"
_client = None


def _get_client():
    global _client
    if _client is None:
        from qdrant_client import AsyncQdrantClient
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        _client.set_model(settings.qdrant_embedding_model)
    return _client


async def ensure_collection() -> None:
    """Crea la colección si no existe."""
    client = _get_client()
    try:
        await client.get_collection(COLLECTION)
    except Exception:
        # La colección no existe — se creará automáticamente en el primer add()
        pass


async def index_objeciones(objeciones: list[dict]) -> None:
    """Indexa la lista de objeciones en Qdrant usando embeddings locales (fastembed).

    Recrea la colección para garantizar que está actualizada.
    """
    client = _get_client()

    # Eliminar colección anterior si existe
    try:
        await client.delete_collection(COLLECTION)
    except Exception:
        pass

    documents = [o["texto"] for o in objeciones]
    metadata = [{"respuesta": o["respuesta"], "categoria": o["categoria"]} for o in objeciones]
    ids = list(range(len(objeciones)))

    await client.add(
        collection_name=COLLECTION,
        documents=documents,
        metadata=metadata,
        ids=ids,
    )
    logger.info("qdrant_objeciones_indexed", extra={"count": len(objeciones)})


async def search_objection(user_text: str, score_threshold: float = 0.4) -> dict | None:
    """Busca la objeción más similar semánticamente al texto del usuario.

    Retorna dict con 'respuesta' y 'categoria', o None si no hay match confiable.
    """
    client = _get_client()
    try:
        results = await client.query(
            collection_name=COLLECTION,
            query_text=user_text,
            limit=1,
            score_threshold=score_threshold,
        )
        if results:
            payload = results[0].metadata
            logger.info("qdrant_objection_found", extra={
                "score": round(results[0].score, 3),
                "categoria": payload.get("categoria"),
            })
            return payload
    except Exception as exc:
        logger.error("qdrant_search_error", extra={"error": str(exc)})
    return None
