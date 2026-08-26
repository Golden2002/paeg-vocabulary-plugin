# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.ipa_enricher — 音标补全（§3.116 模块2 ⭐）。

多口音 IPA：CMU dict（en）+ espeak-ng 兜底 + 常用词手写表。
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional


# 常用词音标手写表（兜底——CMU/espeak 不可用时）
_COMMON_IPA = {
    "the": {"en_us": "/ðə/", "en_uk": "/ðə/"},
    "and": {"en_us": "/ænd/", "en_uk": "/ænd/"},
    "for": {"en_us": "/fɔːr/", "en_uk": "/fɔːr/"},
    "you": {"en_us": "/juː/", "en_uk": "/juː/"},
    "this": {"en_us": "/ðɪs/", "en_uk": "/ðɪs/"},
    "that": {"en_us": "/ðæt/", "en_uk": "/ðæt/"},
    "with": {"en_us": "/wɪð/", "en_uk": "/wɪð/"},
    "from": {"en_us": "/frʌm/", "en_uk": "/frʌm/"},
    "have": {"en_us": "/hæv/", "en_uk": "/hæv/"},
    "not": {"en_us": "/nɒt/", "en_uk": "/nɒt/"},
    "life": {"en_us": "/laɪf/", "en_uk": "/laɪf/"},
    "truth": {"en_us": "/truːθ/", "en_uk": "/truːθ/"},
    "love": {"en_us": "/lʌv/", "en_uk": "/lʌv/"},
    "world": {"en_us": "/wɜːrld/", "en_uk": "/wɜːld/"},
    "light": {"en_us": "/laɪt/", "en_uk": "/laɪt/"},
    "form": {"en_us": "/fɔːrm/", "en_uk": "/fɔːm/"},
    "being": {"en_us": "/ˈbiːɪŋ/", "en_uk": "/ˈbiːɪŋ/"},
    "consciousness": {"en_us": "/ˈkɑːnʃəsnəs/", "en_uk": "/ˈkɒnʃəsnəs/"},
    "knowledge": {"en_us": "/ˈnɑːlɪdʒ/", "en_uk": "/ˈnɒlɪdʒ/"},
    "experience": {"en_us": "/ɪkˈspɪriəns/", "en_uk": "/ɪkˈspɪəriəns/"},
}


class IpaEnricher:
    """音标补全器（多口音：CMU → espeak → 手写表）。"""

    def enrich(self, word: str) -> Dict[str, str]:
        """返回多口音 IPA dict（en_us/en_uk 等）。"""
        w = word.strip().lower()
        # 1. 手写表（快）
        if w in _COMMON_IPA:
            return dict(_COMMON_IPA[w])
        # 2. espeak-ng（IPA 生成）
        try:
            import subprocess
            r = subprocess.run(["espeak-ng", "-q", "--ipa=3", w],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                ipa = f"/{r.stdout.strip().split()[-1]}/"
                return {"en_us": ipa, "en_uk": ipa}
        except Exception:
            pass
        # 3. 兜底：空（由 LLM 补全）
        return {}


def get_ipa(word: str) -> Dict[str, str]:
    """便捷入口。"""
    return IpaEnricher().enrich(word)
