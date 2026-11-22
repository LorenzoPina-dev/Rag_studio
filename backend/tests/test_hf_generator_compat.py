import sys
import types
from typing import Any

from app.providers import huggingface as hf


def _fake_transformers(pipeline_result: Any = None, pipeline_error: Exception | None = None) -> Any:
    module = types.ModuleType("transformers")

    def pipeline(*args: Any, **kwargs: Any) -> Any:
        if pipeline_error is not None:
            raise pipeline_error
        return lambda text, **generate_kwargs: pipeline_result

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model_name: str) -> "FakeTokenizer":
            assert model_name == "fake/seq2seq"
            return cls()

        def __call__(self, text: str, **kwargs: Any) -> dict[str, list[int]]:
            assert kwargs["return_tensors"] == "pt"
            assert kwargs["truncation"] is True
            return {"input_ids": [1, 2]}

        def decode(self, values: Any, **kwargs: Any) -> str:
            assert kwargs["skip_special_tokens"] is True
            return "risposta generata"

    class FakeModel:
        calls: list[dict[str, Any]] = []

        @classmethod
        def from_pretrained(cls, model_name: str) -> "FakeModel":
            assert model_name == "fake/seq2seq"
            return cls()

        def generate(self, **kwargs: Any) -> list[list[int]]:
            self.calls.append(kwargs)
            return [[7, 8]]

    module.pipeline = pipeline
    module.AutoTokenizer = FakeTokenizer
    module.AutoModelForSeq2SeqLM = FakeModel
    return module


async def test_generator_uses_text2text_pipeline_when_available(monkeypatch: Any) -> None:
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        _fake_transformers(pipeline_result=[{"generated_text": "via pipeline"}]),
    )
    generator = hf.HuggingFaceGenerator("fake/seq2seq")
    answer = await generator.generate("domanda")
    assert answer.text == "via pipeline"


async def test_generator_falls_back_to_seq2seq_on_transformers_v5(monkeypatch: Any) -> None:
    fake = _fake_transformers(
        pipeline_error=ValueError("The task text2text-generation has been removed")
    )
    monkeypatch.setitem(sys.modules, "transformers", fake)
    generator = hf.HuggingFaceGenerator("fake/seq2seq")
    answer = await generator.generate("domanda")
    assert answer.text == "risposta generata"
    assert fake.AutoModelForSeq2SeqLM.calls == [
        {"input_ids": [1, 2], "max_new_tokens": 256, "do_sample": False}
    ]
