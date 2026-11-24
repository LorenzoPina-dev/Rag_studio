"""Layout-aware extraction from PDF bytes: text, tables, images and figures.

PyMuPDF provides the geometry; descriptions are deterministic by default and
can be produced by a real vision model through ``describe_visual``.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.providers import settings as provider_settings
from app.providers._common import sanitize

_MAX_PAGES = 2000
_MAX_TEXT_CHARS = 8_000_000
_MAX_TABLES = 20
_MAX_TABLE_ROWS = 100
_MAX_IMAGES = 12
_MAX_IMAGE_BYTES = 1_500_000
_MAX_CAPTION_CHARS = 400
_MAX_LABELS = 12
_MIN_FIGURE_AREA = 0.004  # share of the page area
_CAPTION_WORDS = (
    "figura", "figure", "grafico", "chart", "tabella", "table", "diagramma", "diagram"
)


class ComponentExtractionError(ValueError):
    """PyMuPDF missing, PDF unreadable or encrypted."""


def encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def decode_bytes(value: str) -> bytes:
    return base64.b64decode(value)


def _pymupdf() -> Any:
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise ComponentExtractionError(
            "Estrazione componenti PDF non disponibile: installa PyMuPDF (`pip install pymupdf`)"
        ) from exc
    return pymupdf


def _clean_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def _clean_table(rows: Sequence[Sequence[Any]]) -> list[list[str]]:
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows[:_MAX_TABLE_ROWS]]
    if not cleaned:
        return []
    width = max(len(row) for row in cleaned)
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    useful = [index for index in range(width) if any(row[index] for row in cleaned)]
    cleaned = [[row[index] for index in useful] for row in cleaned]
    while cleaned and not any(cleaned[-1]):
        cleaned.pop()
    return cleaned[:_MAX_TABLE_ROWS]


def _markdown_table(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    width = len(rows[0])
    header = list(rows[0]) + [""] * (width - len(rows[0]))
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join([" --- "] * width) + "|"]
    for row in rows[1:]:
        cells = list(row) + [""] * (width - len(row))
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines)


def _rect_values(rect: Any) -> list[float]:
    return [round(float(value), 1) for value in (rect.x0, rect.y0, rect.x1, rect.y1)]


def _overlaps(first: Any, second: Any, gap: float = 0.0) -> bool:
    return not (
        first.x1 + gap < second.x0
        or second.x1 + gap < first.x0
        or first.y1 + gap < second.y0
        or second.y1 + gap < first.y0
    )


def _caption_for(page: Any, rect: Any, pymupdf: Any) -> str:
    if rect is None:
        return ""
    candidates: list[tuple[int, int, str]] = []
    for block in page.get_text("blocks"):
        if len(block) < 7 or block[6] != 0:
            continue
        text = _clean_cell(block[4])
        if not text:
            continue
        block_rect = pymupdf.Rect(block[:4])
        if block_rect.x1 < rect.x0 or block_rect.x0 > rect.x1:
            continue
        below = block_rect.y0 - rect.y1
        above = rect.y0 - block_rect.y1
        gaps = [gap for gap in (below, above) if gap >= 0]
        distance = min(gaps, default=0.0)
        if distance > 45:
            continue
        is_caption = any(word in text.lower() for word in _CAPTION_WORDS)
        score = (0 if is_caption else 1, round(distance))
        candidates.append((*score, text[:_MAX_CAPTION_CHARS]))
    if not candidates:
        return ""
    return sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]


def _group_drawings(
    drawings: Sequence[dict[str, Any]], gap: float = 15.0
) -> list[list[dict[str, Any]]]:
    """Cluster vector paths that belong to the same chart/diagram."""
    groups: list[list[dict[str, Any]]] = []
    for drawing in drawings:
        rect = drawing["rect"]
        touching = [
            group for group in groups if any(_overlaps(rect, item["rect"], gap) for item in group)
        ]
        if not touching:
            groups.append([drawing])
            continue
        merged = touching[0]
        for group in touching[1:]:
            merged.extend(group)
            groups.remove(group)
        merged.append(drawing)
    return groups


def _text_labels(page: Any, rect: Any, pymupdf: Any) -> list[str]:
    expanded = pymupdf.Rect(rect.x0 - 10, rect.y0 - 10, rect.x1 + 10, rect.y1 + 20)
    labels: list[str] = []
    for block in page.get_text("blocks"):
        if len(block) < 7 or block[6] != 0:
            continue
        if not _overlaps(pymupdf.Rect(block[:4]), expanded):
            continue
        for line in _clean_cell(block[4]).split("\n"):
            line = line.strip()
            if line and len(line) <= 30 and line not in labels:
                labels.append(line)
    return labels[:_MAX_LABELS]


def _figure_summary(page: Any, rect: Any, group: Sequence[dict[str, Any]], pymupdf: Any) -> str:
    items = [item for drawing in group for item in drawing.get("items", [])]
    fills = sum(1 for item in items if item[0] in {"re", "f"})
    lines = sum(1 for item in items if item[0] in {"l", "s"})
    kind = "Grafico a barre" if fills >= 3 else "Grafico" if fills or lines >= 4 else "Diagramma"
    parts = [f"{kind} con {len(items)} elementi vettoriali"]
    labels = _text_labels(page, rect, pymupdf)
    if labels:
        parts.append("etichette rilevate: " + ", ".join(labels))
    return "; ".join(parts) + "."


def _vector_figures(
    page: Any,
    pymupdf: Any,
    *,
    tables: Sequence[dict[str, Any]],
    images: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    page_area = float(page.rect.width * page.rect.height)
    occupied = [pymupdf.Rect(table["bbox"]) for table in tables]
    occupied += [pymupdf.Rect(image["bbox"]) for image in images if image.get("bbox")]
    text_blocks = [
        pymupdf.Rect(block[:4])
        for block in page.get_text("blocks")
        if len(block) >= 7 and block[6] == 0 and _clean_cell(block[4])
    ]
    figures: list[dict[str, Any]] = []
    for group in _group_drawings(page.get_drawings()):
        items = [item for drawing in group for item in drawing.get("items", [])]
        rects = [drawing["rect"] for drawing in group]
        rect = pymupdf.Rect(
            min(item.x0 for item in rects),
            min(item.y0 for item in rects),
            max(item.x1 for item in rects),
            max(item.y1 for item in rects),
        )
        area = float(rect.width * rect.height)
        too_small = len(items) < 4 or rect.width < 60 or rect.height < 60
        if too_small or area < page_area * _MIN_FIGURE_AREA:
            continue
        if any(
            rect.intersects(other)
            and (rect & other).get_area() > min(area, float(other.width * other.height)) * 0.4
            for other in occupied
        ):
            continue
        text_area = sum(
            (rect & block).get_area() for block in text_blocks if rect.intersects(block)
        )
        if text_area > area * 0.5:
            continue
        try:
            pixmap = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            # Alcuni PDF hanno clip degenerati: il pixmap risulta 0x0 e MuPDF
            # non riesce a scrivere l'header PNG. In quel caso salto la figura.
            if pixmap.width <= 0 or pixmap.height <= 0:
                continue
            png = pixmap.tobytes("png")
        except Exception:  # noqa: BLE001 - una figura non valida non deve bloccare il PDF
            continue
        if not png:
            continue
        summary = _figure_summary(page, rect, group, pymupdf)
        figures.append(
            {
                "kind": "chart" if "Grafico" in summary else "figure",
                "page": int(page.number + 1),
                "contentType": "image/png",
                "data": encode_bytes(png),
                "caption": _caption_for(page, rect, pymupdf),
                "summary": summary,
                "bbox": _rect_values(rect),
            }
        )
    return figures


def extract_pdf_components(
    data: bytes,
    *,
    max_pages: int = _MAX_PAGES,
    max_tables: int = _MAX_TABLES,
    max_images: int = _MAX_IMAGES,
) -> dict[str, Any]:
    """Extract text, tables, embedded images and vector figures from one PDF."""
    pymupdf = _pymupdf()
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - malformed PDF surfaces as a clear UI message
        raise ComponentExtractionError(f"PDF non valido ({exc})") from exc
    if document.needs_pass and not document.authenticate(""):
        raise ComponentExtractionError("PDF protetto da password")

    pages: list[str] = []
    tables: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    total_chars = 0
    try:
        for page in document:
            if len(pages) >= max_pages or total_chars >= _MAX_TEXT_CHARS:
                break
            text = (page.get_text("text") or "").strip()
            if text:
                pages.append(text)
                total_chars += len(text)

            page_tables: list[dict[str, Any]] = []
            if len(tables) < max_tables:
                for table in page.find_tables().tables:
                    rows = _clean_table(table.extract() or [])
                    if not rows or not any(any(row) for row in rows):
                        continue
                    rect = pymupdf.Rect(table.bbox)
                    page_tables.append(
                        {
                            "kind": "table",
                            "page": int(page.number + 1),
                            "rows": rows,
                            "markdown": _markdown_table(rows),
                            "caption": _caption_for(page, rect, pymupdf),
                            "bbox": _rect_values(rect),
                        }
                    )
                    if len(tables) + len(page_tables) >= max_tables:
                        break
            tables.extend(page_tables)

            page_images: list[dict[str, Any]] = []
            if len(images) < max_images:
                for item in page.get_images(full=True):
                    xref = item[0]
                    try:
                        payload = document.extract_image(xref)
                    except Exception:  # noqa: BLE001 - one broken image must not lose the text
                        continue
                    raw = payload.get("image") or b""
                    if not raw or len(raw) > _MAX_IMAGE_BYTES:
                        continue
                    rects = page.get_image_rects(xref)
                    rect = rects[0] if rects else None
                    image = {
                        "kind": "image",
                        "page": int(page.number + 1),
                        "contentType": "image/" + str(payload.get("ext") or "png").lower(),
                        "data": encode_bytes(raw),
                        "caption": _caption_for(page, rect, pymupdf),
                        "bbox": _rect_values(rect) if rect is not None else [],
                    }
                    images.append(image)
                    page_images.append(image)
                    if len(images) >= max_images:
                        break

            remaining = max_images - len(images)
            page_figures = _vector_figures(page, pymupdf, tables=page_tables, images=page_images)
            figures.extend(page_figures[:remaining])
    finally:
        document.close()

    return {
        "text": "\n\n".join(pages),
        "pages": len(pages),
        "tables": tables,
        "images": images,
        "figures": figures,
    }


def reference_description(component: Mapping[str, Any]) -> str:
    """Deterministic description built from geometry, captions and chart data."""
    kind = str(component.get("kind") or "image")
    label = {"table": "Tabella", "chart": "Grafico", "figure": "Figura"}.get(kind, "Immagine")
    page = component.get("page")
    parts = [f"{label} {component.get('index', 1)}" + (f", pagina {page}" if page else "")]
    summary = str(component.get("summary") or "").strip()
    caption = str(component.get("caption") or "").strip()
    if summary:
        parts.append(summary)
    if caption:
        parts.append(f"didascalia: {caption}")
    if len(parts) == 1:
        parts.append("contenuto visivo senza didascalia o etichette rilevate")
    return "; ".join(parts) + "."


_VISION_PROMPT = (
    "Descrivi sinteticamente questa immagine o questo grafico in italiano. "
    "Indica il tipo di visualizzazione, le etichette principali e il messaggio "
    "informativo. Rispondi in 1-3 frasi, senza preambolo."
)
VISION_PROMPT = _VISION_PROMPT
DEFAULT_VISION_PROMPT = VISION_PROMPT


def build_vision_prompt(prompt: str, context: str = "") -> str:
    """Compose the final vision prompt, appending optional document context."""
    rendered = str(prompt or VISION_PROMPT).strip()
    if not rendered:
        raise ComponentExtractionError("Il prompt per la visione è vuoto.")
    if context:
        rendered = f"{rendered}\nContesto dal documento: {context}"
    return rendered


async def describe_visual_bytes(
    data: bytes,
    *,
    provider: str,
    model: str = "",
    prompt: str = VISION_PROMPT,
    content_type: str = "image/png",
    context: str = "",
) -> str:
    """Describe real image bytes with an actual vision provider. No silent fallback."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ComponentExtractionError("Nessun byte immagine disponibile per la descrizione.")
    mode = str(provider or "auto").strip().lower()
    settings = provider_settings.effective_settings()
    if mode == "auto":
        mode = "openai" if (settings.openai_api_key or "").strip() else "ollama"
    if mode not in {"openai", "ollama"}:
        raise ComponentExtractionError(f"Provider visione non supportato: {mode}")
    full_prompt = build_vision_prompt(prompt, context)
    encoded = encode_bytes(bytes(data))

    if mode == "openai":
        from openai import AsyncOpenAI

        if not (settings.openai_api_key or "").strip():
            raise ComponentExtractionError(
                "Servono OPENAI_API_KEY o openai_api_key per la descrizione con visione OpenAI."
            )
        client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        try:
            response = await client.chat.completions.create(
                model=model or settings.openai_vision_model or settings.openai_chat_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": full_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                            },
                        ],
                    }
                ],
                max_tokens=200,
            )
        except Exception as exc:  # noqa: BLE001 - SDK errors vary by endpoint
            raise ComponentExtractionError(
                f"Descrizione visione OpenAI fallita: {sanitize(exc, settings.openai_api_key)}"
            ) from exc
        text = str(response.choices[0].message.content or "").strip()
        if not text:
            raise ComponentExtractionError(
                "OpenAI non ha restituito alcuna descrizione dell'immagine."
            )
        return text

    import httpx

    base_url = settings.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": (
                        model
                        or settings.ollama_vision_model
                        or settings.ollama_chat_model
                    ),
                    "prompt": full_prompt,
                    "images": [encoded],
                    "stream": False,
                },
            )
            response.raise_for_status()
            text = str(response.json().get("response") or "").strip()
    except Exception as exc:  # noqa: BLE001 - network/SDK errors vary
        raise ComponentExtractionError(
            f"Descrizione visione Ollama fallita: {sanitize(exc, None)}"
        ) from exc
    if not text:
        raise ComponentExtractionError(
            "Ollama non ha restituito alcuna descrizione dell'immagine."
        )
    return text


async def describe_visual(component: Mapping[str, Any], mode: str, model: str = "") -> str:
    """Describe a visual with a real vision model. No silent fallback."""
    mode = str(mode or "reference").strip().lower()
    if mode == "off":
        return ""
    if mode == "reference":
        return reference_description(component)
    try:
        data = decode_bytes(str(component.get("data") or ""))
    except Exception as exc:  # noqa: BLE001 - malformed base64 must surface as extraction error
        raise ComponentExtractionError(f"Dati immagine non validi: {exc}") from exc
    context = " ".join(
        str(component.get(key) or "") for key in ("caption", "summary") if component.get(key)
    )
    return await describe_visual_bytes(
        data,
        provider=mode,
        model=model,
        prompt=VISION_PROMPT,
        content_type=str(component.get("contentType") or "image/png"),
        context=context,
    )
