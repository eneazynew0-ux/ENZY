from pathlib import Path

from mlx_vlm import generate
from mlx_vlm.utils import load_model, StoppingCriteria
from mlx_vlm.tokenizer_utils import load_tokenizer

from transformers import AutoTokenizer
from transformers.models.idefics3.image_processing_pil_idefics3 import (
    Idefics3ImageProcessorPil,
)
from transformers.models.idefics3.processing_idefics3 import Idefics3Processor


MODEL_PATH = (
    Path.home()
    / ".cache/huggingface/hub/models--mlx-community--SmolVLM-Instruct-4bit"
    / "snapshots/1cefe9ed9d1971a6ea803dd367db858e0a7cd0d6"
)

IMAGE_SEQ_LEN = 81

_MODEL = None
_PROCESSOR = None


def load_visual_model():
    global _MODEL, _PROCESSOR

    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Vision model not found: {MODEL_PATH}")

    model = load_model(MODEL_PATH)

    image_processor = Idefics3ImageProcessorPil.from_pretrained(MODEL_PATH)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

    processor = Idefics3Processor(
        image_processor=image_processor,
        tokenizer=tokenizer,
        image_seq_len=IMAGE_SEQ_LEN,
    )

    detokenizer_class = load_tokenizer(
        MODEL_PATH,
        return_tokenizer=False,
    )

    processor.detokenizer = detokenizer_class(processor.tokenizer)

    processor.tokenizer.stopping_criteria = StoppingCriteria(
        processor.tokenizer.eos_token_id,
        processor.tokenizer,
    )

    _MODEL = model
    _PROCESSOR = processor

    return _MODEL, _PROCESSOR


def describe_image(image_path, max_tokens=40):
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"Image is empty: {path}")

    model, processor = load_visual_model()

    prompt = (
        "<image> Describe the main physical subject visible in this image "
        "in one short factual sentence. Ignore speculation about identity or history."
    )

    result = generate(
        model,
        processor,
        prompt,
        image=str(path),
        verbose=False,
        max_tokens=max_tokens,
        temperature=0,
    )

    text = result.text if hasattr(result, "text") else str(result)

    return " ".join(text.strip().split())


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m engine.visual_relevance IMAGE_PATH"
        )

    print(describe_image(sys.argv[1]))
