from pathlib import Path

from mlx_vlm import generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load


MODEL_PATH = (
    Path.home()
    / ".cache/huggingface/hub/models--mlx-community--SmolVLM-Instruct-4bit"
    / "snapshots/1cefe9ed9d1971a6ea803dd367db858e0a7cd0d6"
)

_MODEL = None
_PROCESSOR = None


def load_visual_model():
    global _MODEL, _PROCESSOR

    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Vision model not found: {MODEL_PATH}")

    model, processor = load(str(MODEL_PATH))

    _MODEL = model
    _PROCESSOR = processor

    return _MODEL, _PROCESSOR


def describe_image(image_path, max_tokens=60):
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"Image is empty: {path}")

    model, processor = load_visual_model()

    instruction = (
        "Describe only the visible image in one or two factual sentences. "
        "State the main subject's object type, shape, material, and any visible "
        "surface markings, writing, or carved details. Do not identify its history, "
        "repeat these instructions, or add facts that are not visible."
    )
    prompt = apply_chat_template(
        processor,
        model.config,
        instruction,
        add_generation_prompt=True,
        num_images=1,
    )

    result = generate(
        model,
        processor,
        prompt,
        image=str(path),
        verbose=False,
        max_tokens=max_tokens,
        temperature=0,
        repetition_penalty=1.15,
        repetition_context_size=64,
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
