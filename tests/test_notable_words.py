# -*- coding: utf-8 -*-
"""P7 ⭐ 语义显著词保护测试（moonlighting 类——第二标准 is_important）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.notable_words import (
    is_semantically_notable, notable_words, SEMANTICALLY_NOTABLE,
)
from paeg_vocabulary.core.entry import CandidateWord
from paeg_vocabulary.core.context import VocabularyContext
from paeg_vocabulary.quantile_filter import (
    quantile_filter_candidates, _is_important_word,
)


# ── R1: 语义显著词识别 ──
def test_notable_known_words():
    """语义隐喻词（watershed/touchstone 类）。"""
    assert is_semantically_notable("watershed") is True
    assert is_semantically_notable("touchstone") is True
    assert is_semantically_notable("breakthrough") is True


def test_notable_ordinary_words():
    """普通词不误判。"""
    assert is_semantically_notable("table") is False
    assert is_semantically_notable("book") is False
    assert is_semantically_notable("photosynthesis") is False


def test_moonlight_is_polysemy_not_notable():
    """§3.116 ⭐ moonlight 是熟词生义（归 idiom_enricher），非语义显著词。"""
    from paeg_vocabulary.enrichers.idiom_enricher import detect_polysemy
    assert detect_polysemy("moonlight") is not None, "moonlight 应被熟词生义检测"
    assert "兼职" in detect_polysemy("moonlight"), "moonlight 熟词生义应含兼职义项"


# ── R2: is_important 纳入 ──
def test_important_semantic_word():
    """语义显著词 → is_important（频率地板≥2 时）。"""
    cand = CandidateWord(headword="watershed", lemma="watershed", freq_count=3)
    assert _is_important_word(cand, None, min_freq=2) is True


def test_important_semantic_low_freq():
    """语义显著但频次 1 → 频率地板拦（非重要）。"""
    cand = CandidateWord(headword="watershed", lemma="watershed", freq_count=1)
    assert _is_important_word(cand, None, min_freq=2) is False


# ── R3: 筛选保留 ──
def test_filter_keeps_notable():
    """语义显著词即使 Q < U 也保留（第二标准豁免）。"""
    cands = [
        CandidateWord(headword="watershed", lemma="watershed", freq_count=3,
                      global_zipf=2.5, cefr_guess="C1"),
        CandidateWord(headword="the", lemma="the", freq_count=100,
                      global_zipf=7.7, cefr_guess="A1"),
    ]

    class T:
        def __init__(self, w):
            self.lemma = w
    ctx = VocabularyContext(pdf_path="t.pdf", target_lang="en")
    ctx.clean_corpus = [T(c.headword) for c in cands for _ in range(c.freq_count)]
    ctx = quantile_filter_candidates(ctx, u_level=0.99)  # 极高 U——只有豁免能保留
    kept = {c.headword for c in ctx.candidates}
    assert "watershed" in kept, "语义显著词应被第二标准豁免"
    assert "the" not in kept  # 虚词不可豁免
