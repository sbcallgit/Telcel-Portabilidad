"""Utilidades compartidas de los nodos del agente de portabilidad."""

from langchain_core.messages import AIMessage

MAX_BUBBLE_CHARS = 160


def _split_at_boundary(text: str, max_chars: int) -> list[str]:
    """Divide `text` en segmentos de hasta `max_chars` caracteres.

    Orden de prioridad para el punto de corte:
      1. Doble salto de línea (\\n\\n) — separador de párrafos.
      2. Salto de línea simple (\\n) — listas / fin de línea.
      3. Fin de oración (. / ? / ! seguido de espacio).
      4. Último espacio antes del límite — nunca corta a media palabra.
    """
    if len(text) <= max_chars:
        return [text]

    segments: list[str] = []
    remaining = text

    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = -1

        # 1. Párrafo
        pos = window.rfind("\n\n")
        if pos > max_chars // 4:
            cut = pos

        # 2. Salto de línea simple
        if cut == -1:
            pos = window.rfind("\n")
            if pos > max_chars // 4:
                cut = pos

        # 3. Fin de oración
        if cut == -1:
            for sep in (". ", "? ", "! ", ".\n", "?\n", "!\n"):
                pos = window.rfind(sep)
                if pos > max_chars // 4:
                    cut = pos + len(sep) - 1  # incluye el punto/signo
                    break

        # 4. Último espacio (fallback — nunca corta media palabra)
        if cut == -1:
            pos = window.rfind(" ")
            cut = pos if pos > 0 else max_chars

        head = remaining[:cut].strip()
        if head:
            segments.append(head)
        remaining = remaining[cut:].strip()

    if remaining:
        segments.append(remaining)

    return [s for s in segments if s]


def split_msg(text: str, max_chars: int = MAX_BUBBLE_CHARS) -> list[AIMessage]:
    """Divide la respuesta de Claude en burbujas de chat.

    Primero respeta los separadores explícitos `|||` que el modelo puede insertar;
    luego aplica el límite de caracteres a cada segmento resultante.
    """
    primary = [s.strip() for s in text.split("|||")]
    primary = [s for s in primary if s]

    all_segments: list[str] = []
    for segment in primary:
        all_segments.extend(_split_at_boundary(segment, max_chars))

    return [AIMessage(content=s) for s in all_segments] if all_segments else [AIMessage(content=text)]
