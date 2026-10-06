"""All engine classes. engines.py is the registry mapping engine keys to these."""

from .google import GoogleTranslator
from .bing import BingTranslator
from .deepl import DeepLTranslator
from .baidu import BaiduTranslator, BaiduPlaywrightTranslator
from .yandex import YandexTranslator
from .wwwjdic import WwwjdicTranslator
from .jisho import JishoTranslator
from .babelfish import BabelfishTranslator
from .papago import PapagoTranslator
from .caiyun import CaiyunTranslator
from .systran import SystranTranslator
from .babylon import BabylonTranslator
from .lec import LecTranslator
from .openai_compat import OpenAICompatTranslator

__all__ = [
    "GoogleTranslator",
    "BingTranslator",
    "DeepLTranslator",
    "BaiduTranslator",
    "BaiduPlaywrightTranslator",
    "YandexTranslator",
    "WwwjdicTranslator",
    "JishoTranslator",
    "BabelfishTranslator",
    "PapagoTranslator",
    "CaiyunTranslator",
    "SystranTranslator",
    "BabylonTranslator",
    "LecTranslator",
    "OpenAICompatTranslator",
]
