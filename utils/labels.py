"""Display labels for internal setting values."""
from __future__ import annotations


QUALITY_LABELS = {
    "ru": {
        "low": "Быстро",
        "medium": "Баланс",
        "high": "Красиво",
        "lossless": "Максимум",
    },
    "en": {
        "low": "Fast",
        "medium": "Balanced",
        "high": "Beautiful",
        "lossless": "Maximum",
    },
}


def quality_label(value: str, lang: str) -> str:
    return QUALITY_LABELS.get(lang, QUALITY_LABELS["ru"]).get(value, value)
