"""Cliente Qdrant para RAG semántico de objeciones.

Usa fastembed (local) con un modelo multilingüe — sin API key de embeddings.
"""

import logging
import uuid

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


def _is_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code == 404 or getattr(response, "status_code", None) == 404:
        return True

    error_text = str(exc).lower()
    return "not found" in error_text or "does not exist" in error_text or "doesn't exist" in error_text


def _is_alias_name_conflict(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    error_text = str(exc).lower()
    has_conflict_status = (
        status_code in (400, 409)
        or response_status in (400, 409)
        or "status code: 400" in error_text
        or "status code: 409" in error_text
    )
    has_conflict_text = "already exists" in error_text or "same name" in error_text
    return has_conflict_status and has_conflict_text


async def _delete_collection_if_exists(client, collection_name: str) -> None:
    try:
        await client.delete_collection(collection_name)
    except Exception as exc:
        if _is_not_found_error(exc):
            return
        raise


async def _current_alias_target(client, alias_name: str) -> str | None:
    if not hasattr(client, "get_aliases"):
        return None

    aliases_response = await client.get_aliases()
    for alias in getattr(aliases_response, "aliases", []) or []:
        if getattr(alias, "alias_name", None) == alias_name:
            return getattr(alias, "collection_name", None)
    return None


async def _point_alias_to_collection(client, collection_name: str) -> str | None:
    from qdrant_client.http import models

    current_target = await _current_alias_target(client, COLLECTION)
    operations = []
    if current_target:
        operations.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=COLLECTION)))
    operations.append(
        models.CreateAliasOperation(
            create_alias=models.CreateAlias(collection_name=collection_name, alias_name=COLLECTION)
        )
    )

    await client.update_collection_aliases(change_aliases_operations=operations)
    return current_target


async def ensure_collection() -> None:
    """Crea la colección si no existe."""
    client = _get_client()
    try:
        await client.get_collection(COLLECTION)
    except Exception as exc:
        if not _is_not_found_error(exc):
            logger.error("qdrant_collection_check_error", extra={"error": str(exc)})
            raise
        # La colección no existe — se creará automáticamente en el primer add()
        pass


async def index_objeciones(objeciones: list[dict]) -> None:
    """Indexa la lista de objeciones en Qdrant usando embeddings locales (fastembed).

    Reindexa en una colección temporal y solo reemplaza el alias estable
    cuando el add terminó correctamente.
    """
    client = _get_client()
    temp_collection = f"{COLLECTION}_reindex_{uuid.uuid4().hex}"

    documents = [o["texto"] for o in objeciones]
    metadata = [{"respuesta": o["respuesta"], "categoria": o["categoria"]} for o in objeciones]
    ids = list(range(len(objeciones)))

    await client.add(
        collection_name=temp_collection,
        documents=documents,
        metadata=metadata,
        ids=ids,
    )

    previous_alias_target = None
    try:
        previous_alias_target = await _point_alias_to_collection(client, temp_collection)
    except Exception as exc:
        if not _is_alias_name_conflict(exc):
            logger.error("qdrant_alias_swap_failed", extra={"temp_collection": temp_collection, "error": str(exc)})
            raise

        logger.info("qdrant_alias_migration_from_collection", extra={"error": str(exc)})
        try:
            await _delete_collection_if_exists(client, COLLECTION)
            previous_alias_target = await _point_alias_to_collection(client, temp_collection)
        except Exception:
            logger.error("qdrant_alias_swap_failed", extra={"temp_collection": temp_collection})
            raise

    if previous_alias_target and previous_alias_target != temp_collection:
        await _delete_collection_if_exists(client, previous_alias_target)

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
