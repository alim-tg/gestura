import urllib.request
from pathlib import Path

from .config import MODEL_PATH, MODEL_URL, MODELS


def ensure_model() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH
    MODELS.mkdir(parents=True, exist_ok=True)
    print(f"downloading {MODEL_URL}")
    partial = MODEL_PATH.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, partial)
    partial.replace(MODEL_PATH)
    print(f"saved {MODEL_PATH} ({MODEL_PATH.stat().st_size // 1024} KB)")
    return MODEL_PATH
