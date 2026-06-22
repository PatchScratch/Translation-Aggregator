"""translation_aggregator package"""
from .base import Translator, Language, TranslationResult
from .aggregator import TranslatorAggregator
from .translators import (
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    BaiduTranslator,
    YandexTranslator,
)

__all__ = [
    "Translator",
    "Language",
    "TranslationResult",
    "TranslatorAggregator",
    "GoogleTranslator",
    "BingTranslator",
    "DeepLTranslator",
    "BaiduTranslator",
    "YandexTranslator",
]
