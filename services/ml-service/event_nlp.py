"""Optional on-disk FinBERT sentiment inference; never downloads model weights."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=2)
def _load(model_dir: str) -> tuple[Any, Any, Any]:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch

    path = Path(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        path, local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    model.eval()
    return tokenizer, model, torch


def classify(model_dir: str, text: str) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("Event text is empty")
    tokenizer, model, torch = _load(str(Path(model_dir).resolve()))
    batch = tokenizer(text[:12000], return_tensors="pt", truncation=True, max_length=512)
    with torch.inference_mode():
        logits = model(**batch).logits[0]
        probabilities = torch.softmax(logits, dim=-1).tolist()
    labels = {int(key): str(value).lower() for key, value in model.config.id2label.items()}
    scores = {labels[index]: float(score) for index, score in enumerate(probabilities)}
    label = max(scores, key=scores.get)
    normalized = "positive" if "positive" in label else "negative" if "negative" in label else "neutral"
    return {"sentiment": normalized, "confidence": round(scores[label], 4),
            "model": Path(model_dir).name, "scores": scores}
