"""Test dell'estrattore multimediale dei PDF e del nodo Document Processing."""

from __future__ import annotations

from pathlib import Path

import pytest

import app.components.builtin.reference_nodes as reference_nodes
from app.components import dataset_connectors
from app.components.builtin.reference_nodes import (
    DocumentComponentExtractionNode,
    VisualContentExtractorNode,
)
from app.components.document_components import (
    ComponentExtractionError,
    decode_bytes,
    describe_visual,
    describe_visual_bytes,
    extract_pdf_components,
    reference_description,
)
from app.core.bootstrap import container
from app.domain.contracts.data import ArtifactRef, Document, Query, SourceRef
from app.domain.contracts.node import NodeConfig
from app.infrastructure.memory import store

pytest.importorskip("pymupdf")


def make_pdf() -> bytes:
    import pymupdf

    pdf = pymupdf.open()
    page = pdf.new_page(width=600, height=800)
    page.insert_text((50, 50), "Report 2024", fontsize=16)
    page.insert_text((50, 90), "Le vendite sono cresciute.", fontsize=11)

    columns = [50, 150, 250, 350]
    rows = [120, 150, 180, 210]
    values = [["Anno", "Valore"], ["2023", "12"], ["2024", "18"]]
    for y in rows:
        page.draw_line((columns[0], y), (columns[-1], y))
    for x in columns[:3]:
        page.draw_line((x, rows[0]), (x, rows[-1]))
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            page.insert_text((columns[column_index] + 6, rows[row_index] + 20), value, fontsize=10)
    page.insert_text((50, 225), "Tabella 1: vendite annue", fontsize=9)

    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 30, 30))
    pixmap.set_rect(pixmap.irect, (200, 30, 30))
    page.insert_image(pymupdf.Rect(400, 100, 500, 200), stream=pixmap.tobytes("png"))
    page.insert_text((400, 215), "Figura 1: logo", fontsize=9)

    page.draw_line((50, 700), (250, 700))
    page.draw_line((50, 500), (50, 700))
    for index, (x, height) in enumerate([(70, 80), (110, 140), (150, 110), (190, 170)]):
        page.draw_rect(pymupdf.Rect(x, 700 - height, x + 25, 700), fill=(0.3, 0.5, 0.9))
        page.insert_text((x + 4, 715), str(2019 + index), fontsize=8)
    page.insert_text((50, 490), "Grafico 1: andamento", fontsize=9)
    return pdf.tobytes()


class FakeContext:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.artifacts: dict[str, bytes] = {}

    def log(self, level: str, message: str, **fields: object) -> None:
        self.logs.append(message)

    def is_cancelled(self) -> bool:
        return False

    async def store_artifact(self, name: str, data: object, **kwargs: object) -> ArtifactRef:
        self.artifacts[name] = data if isinstance(data, bytes) else b""
        return ArtifactRef(artifact_id=f"art_{name}", uri=f"memory://{name}")


def test_extract_pdf_components_finds_text_table_image_and_chart():
    extracted = extract_pdf_components(make_pdf())

    assert "Report 2024" in extracted["text"]
    assert extracted["pages"] == 1
    assert len(extracted["tables"]) == 1
    assert extracted["tables"][0]["rows"][0][:2] == ["Anno", "Valore"]
    assert "| Anno | Valore |" in extracted["tables"][0]["markdown"]
    assert "Tabella 1" in extracted["tables"][0]["caption"]
    assert len(extracted["images"]) == 1
    assert "Figura 1" in extracted["images"][0]["caption"]
    assert len(extracted["figures"]) == 1
    assert extracted["figures"][0]["kind"] == "chart"
    assert "Grafico 1" in extracted["figures"][0]["caption"]
    assert "2019" in extracted["figures"][0]["summary"]


def test_figures_are_not_suppressed_by_images_on_other_pages():
    import pymupdf

    pdf = pymupdf.open()
    first = pdf.new_page(width=600, height=800)
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 30, 30))
    pixmap.set_rect(pixmap.irect, (200, 30, 30))
    first.insert_image(pymupdf.Rect(400, 100, 500, 200), stream=pixmap.tobytes("png"))

    second = pdf.new_page(width=600, height=800)
    for x in (410, 440, 470):
        second.draw_rect(pymupdf.Rect(x, 110, x + 20, 190), fill=(0.3, 0.5, 0.9))
    second.draw_rect(pymupdf.Rect(400, 100, 500, 200), fill=None)

    extracted = extract_pdf_components(pdf.tobytes())
    assert len(extracted["images"]) == 1
    assert any(figure["page"] == 2 for figure in extracted["figures"])


def test_connector_attaches_components_to_pdf_documents():
    documents = dataset_connectors._pdf_documents(make_pdf(), "report.pdf", "/data/report.pdf")

    assert len(documents) == 1
    assert documents[0]["fileType"] == "pdf"
    assert documents[0]["content"].startswith("Report 2024")
    assert len(documents[0]["components"]["tables"]) == 1
    assert len(documents[0]["components"]["images"]) == 1


async def test_node_merges_descriptions_and_stores_visuals():
    extracted = extract_pdf_components(make_pdf())
    document = Document(
        id="doc_report",
        content=extracted["text"],
        title="report.pdf",
        source=SourceRef(uri="/data/report.pdf", title="report.pdf"),
        metadata={"components": {key: extracted[key] for key in ("tables", "images", "figures")}},
    )
    context = FakeContext()
    node = DocumentComponentExtractionNode()
    result = await node.execute(
        {"in_documents": [document]},
        NodeConfig(values={"descriptionMode": "reference", "mergeIntoText": True}),
        context,
    )

    enriched = result.outputs["out_documents"][0]
    assert isinstance(enriched, Document)
    assert "## Tabelle" in enriched.content
    assert "| Anno | Valore |" in enriched.content
    assert "## Immagini e grafici" in enriched.content
    assert "Grafico 1: andamento" in enriched.content
    assert enriched.metadata["enrichment"] == {
        "tables": 1, "images": 1, "figures": 1, "descriptionMode": "reference", "merged": True
    }
    assert len(result.outputs["out_components"]) == 2
    assert all("data" not in item for item in result.outputs["out_components"])
    assert len(context.artifacts) == 2
    visuals = (extracted["images"][0], extracted["figures"][0])
    assert all(decode_bytes(item["data"]) for item in visuals)
    assert result.metrics["described"] == 2
    assert any("reference" in warning for warning in result.warnings)


async def test_node_extracts_from_local_pdf_path_when_metadata_is_missing(tmp_path: Path):
    path = tmp_path / "inline.pdf"
    path.write_bytes(make_pdf())
    document = Document(id="doc_inline", content="", source=SourceRef(uri=str(path)))
    context = FakeContext()

    result = await DocumentComponentExtractionNode().execute(
        {"in_documents": [document]}, NodeConfig(values={"descriptionMode": "off"}), context
    )

    assert result.metrics["tables"] == 1
    assert "## Tabelle" in result.outputs["out_documents"][0].content
    assert result.metrics["described"] == 0


async def test_node_can_disable_parts_and_merge():
    extracted = extract_pdf_components(make_pdf())
    document = Document(
        id="doc_report", content="Original text",
        metadata={"components": {key: extracted[key] for key in ("tables", "images", "figures")}},
    )
    result = await DocumentComponentExtractionNode().execute(
        {"in_documents": [document]},
        NodeConfig(
            values={"extractTables": False, "extractImages": False, "extractFigures": False}
        ),
        FakeContext(),
    )

    assert result.outputs["out_documents"][0].content == "Original text"
    assert result.metrics["tables"] == 0
    assert result.outputs["out_components"] == []


async def test_node_describes_and_stores_without_merging():
    extracted = extract_pdf_components(make_pdf())
    document = Document(
        id="doc_report",
        content="Original text",
        metadata={"components": {key: extracted[key] for key in ("tables", "images", "figures")}},
    )
    context = FakeContext()

    result = await DocumentComponentExtractionNode().execute(
        {"in_documents": [document]},
        NodeConfig(values={"mergeIntoText": False}),
        context,
    )

    assert result.outputs["out_documents"][0].content == "Original text"
    assert result.metrics["described"] == 2
    assert len(context.artifacts) == 2
    assert all("description" in item for item in result.outputs["out_components"])


async def test_reference_description_and_mode_validation():
    visual = {
        "kind": "chart",
        "page": 2,
        "index": 1,
        "summary": "Barre: 4.",
        "caption": "Grafico vendite",
    }
    description = await describe_visual(visual, "reference")
    assert description == reference_description(visual)
    assert "Grafico 1" in description
    assert "Grafico vendite" in description
    errors = DocumentComponentExtractionNode().validate_config(
        NodeConfig(values={"descriptionMode": "unknown"})
    )
    assert any("descriptionMode" in error for error in errors)


def test_node_is_exposed_in_catalog_and_registry():
    assert any(item.id == "document-component-extraction" for item in store.node_definitions)
    assert container.node_registry.get_spec("document-component-extraction") is not None
    assert isinstance(
        container.node_registry.get_implementation("document-component-extraction"),
        DocumentComponentExtractionNode,
    )


class FakeVisionContext:
    def __init__(self, artifacts: dict[str, bytes]) -> None:
        self.artifacts = artifacts
        self.loaded: list[str] = []
        self.logs: list[str] = []

    def log(self, level: str, message: str, **fields: object) -> None:
        self.logs.append(message)

    def is_cancelled(self) -> bool:
        return False

    async def load_artifact(self, ref: object) -> bytes:
        artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else str(ref)
        self.loaded.append(artifact_id)
        return self.artifacts[artifact_id]


def _visual_component(
    *,
    kind: str,
    artifact: object,
    caption: str = "",
    summary: str = "",
    page: int = 1,
) -> dict[str, object]:
    return {
        "kind": kind,
        "page": page,
        "caption": caption,
        "summary": summary,
        "contentType": "image/png",
        "artifact": artifact.model_dump(mode="json")
        if isinstance(artifact, ArtifactRef)
        else artifact,
    }


async def test_visual_extractor_uses_artifact_bytes_with_context_and_provenance(monkeypatch):
    image_ref = ArtifactRef(artifact_id="art_image", uri="memory://art_image")
    chart_ref = ArtifactRef(artifact_id="art_chart", uri="memory://art_chart")
    context = FakeVisionContext(
        {"art_image": b"REAL-PNG-BYTES", "art_chart": b"REAL-CHART-BYTES"}
    )
    calls: list[dict[str, object]] = []

    async def fake_vision(
        data: bytes,
        *,
        provider: str,
        model: str,
        prompt: str,
        content_type: str,
        context: str,
    ) -> str:
        calls.append(
            {
                "data": data,
                "provider": provider,
                "model": model,
                "prompt": prompt,
                "contentType": content_type,
                "context": context,
            }
        )
        return f"Testo visione {len(calls)}"

    monkeypatch.setattr(reference_nodes, "describe_visual_bytes", fake_vision)
    result = await VisualContentExtractorNode().execute(
        {
            "in_components": [
                _visual_component(
                    kind="image", artifact=image_ref, caption="Figura 1: emissioni", page=3
                ),
                _visual_component(
                    kind="chart", artifact="art_chart", summary="Barre 2024", page=4
                ),
                _visual_component(kind="image", artifact="art_no_context"),
                _visual_component(kind="table", artifact="art_table", caption="Tabella 1"),
            ],
            "in_query": Query(id="q1", text="emissioni"),
        },
        NodeConfig(
            values={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "prompt": "Analizza {kind} a pagina {page} ({caption}) per {query}: {summary}",
                "requireContext": True,
                "maxVisuals": 5,
            }
        ),
        context,
    )

    assert result.status == "completed"
    assert result.metrics["components"] == 4
    assert result.metrics["eligible"] == 3
    assert result.metrics["skippedNoContext"] == 1
    assert result.metrics["described"] == 2
    assert context.loaded == ["art_image", "art_chart"]
    assert [call["data"] for call in calls] == [b"REAL-PNG-BYTES", b"REAL-CHART-BYTES"]
    assert all(call["provider"] == "openai" for call in calls)
    assert all(call["model"] == "gpt-4o-mini" for call in calls)
    assert "Figura 1: emissioni" in str(calls[0]["prompt"])
    assert "emissioni" in str(calls[0]["prompt"])
    assert "Barre 2024" in str(calls[1]["prompt"])
    assert "didascalia: Figura 1: emissioni" in str(calls[0]["prompt"])
    assert str(calls[0]["context"]) == "Figura 1: emissioni"

    documents = result.outputs["out_documents"]
    assert [document.id for document in documents] == ["visual_art_image", "visual_art_chart"]
    assert [document.content for document in documents] == ["Testo visione 1", "Testo visione 2"]
    assert documents[0].metadata["page"] == 3
    assert documents[0].metadata["artifactId"] == "art_image"
    assert documents[0].metadata["visualRefs"][0]["caption"] == "Figura 1: emissioni"
    assert documents[0].source is not None
    assert documents[0].source.uri == "artifact://art_image"

    texts = result.outputs["out_visual_text"]
    assert [item["artifactId"] for item in texts] == ["art_image", "art_chart"]
    assert texts[0]["page"] == 3
    assert texts[1]["caption"] == ""
    assert texts[0]["provider"] == "openai"


async def test_visual_extractor_can_include_visuals_without_context(monkeypatch):
    context = FakeVisionContext({"art_plain": b"PNG"})
    seen: list[bytes] = []

    async def fake_vision(data: bytes, **kwargs: object) -> str:
        seen.append(data)
        return "Solo byte reali"

    monkeypatch.setattr(reference_nodes, "describe_visual_bytes", fake_vision)
    result = await VisualContentExtractorNode().execute(
        {"in_components": [_visual_component(kind="image", artifact="art_plain")]},
        NodeConfig(values={"requireContext": False}),
        context,
    )

    assert result.status == "completed"
    assert result.metrics["skippedNoContext"] == 0
    assert result.metrics["described"] == 1
    assert seen == [b"PNG"]


async def test_visual_extractor_fails_loudly_without_a_vision_provider(monkeypatch):
    context = FakeVisionContext({"art_image": b"PNG"})

    async def missing_provider(*args: object, **kwargs: object) -> str:
        raise ComponentExtractionError("Nessun provider visione configurato")

    monkeypatch.setattr(reference_nodes, "describe_visual_bytes", missing_provider)
    result = await VisualContentExtractorNode().execute(
        {
            "in_components": [
                _visual_component(kind="image", artifact="art_image", caption="Figura 1")
            ]
        },
        NodeConfig(values={"provider": "openai"}),
        context,
    )

    assert result.status == "failed"
    assert result.outputs["out_documents"] == []
    assert any("Nessun provider visione" in error for error in result.errors)


async def test_visual_extractor_completes_without_eligible_visuals():
    result = await VisualContentExtractorNode().execute(
        {"in_components": [_visual_component(kind="table", artifact="art_table", caption="T1")]},
        NodeConfig(values={}),
        FakeVisionContext({}),
    )

    assert result.status == "completed"
    assert result.metrics["eligible"] == 0
    assert result.outputs["out_documents"] == []


async def test_describe_visual_bytes_requires_real_bytes():
    with pytest.raises(ComponentExtractionError, match="Nessun byte immagine"):
        await describe_visual_bytes(b"", provider="openai")


async def test_describe_visual_bytes_masks_api_key_in_errors(monkeypatch):
    openai = pytest.importorskip("openai")

    class FakeCompletions:
        async def create(self, **kwargs: object) -> object:
            raise RuntimeError("boom sk-super-secret")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.chat = FakeChat()

    from app.components import document_components

    class FakeSettings:
        openai_api_key = "sk-super-secret"
        openai_base_url = "https://example.test/v1"
        openai_vision_model = "vision-test"
        openai_chat_model = "chat-test"
        ollama_base_url = "http://127.0.0.1:11434"
        ollama_vision_model = "llava"
        ollama_chat_model = "llama3.2:1b"

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    monkeypatch.setattr(document_components.provider_settings, "effective_settings", lambda: FakeSettings())

    with pytest.raises(ComponentExtractionError) as exc:
        await describe_visual_bytes(b"REAL-PNG", provider="openai")
    assert "sk-super-secret" not in str(exc.value)
    assert "***" in str(exc.value)


def test_visual_extractor_is_exposed_in_catalog_and_registry():
    assert any(item.id == "visual-content-extractor" for item in store.node_definitions)
    spec = container.node_registry.get_spec("visual-content-extractor")
    assert spec is not None
    assert spec.kind == "processor"
    assert any(parameter.key == "prompt" for parameter in spec.parameters)
    assert isinstance(
        container.node_registry.get_implementation("visual-content-extractor"),
        VisualContentExtractorNode,
    )
    errors = VisualContentExtractorNode().validate_config(
        NodeConfig(values={"provider": "unknown"})
    )
    assert any("provider" in error for error in errors)
