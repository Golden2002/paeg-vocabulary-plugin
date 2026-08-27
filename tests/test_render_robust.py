# -*- coding: utf-8 -*-
"""P7 ⭐ 渲染健壮性测试（morpheme prefix/suffix 为 list 不崩溃）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.entry import VocabularyEntry, Morpheme
from paeg_vocabulary.render.entry_html import entry_to_html


def _full_entry():
    return VocabularyEntry(
        headword="phenomenology", pos="n.",
        ipa={"en_us": "/fɪ/"},
        gloss_bilingual={"zh": "现象学", "en": "study of consciousness"},
        examples=[{"en": "Example.", "zh": "例句。"}],
        lemma="phenomenology",
    )


def test_suffix_as_list():
    """suffix 为 list（LLM 返回变体）→ 渲染不崩溃。"""
    e = _full_entry()
    e.morpheme = Morpheme(
        roots=[{"root": "phainomenon", "lang": "Greek", "meaning": "appearance"}],
        prefix=None,
        suffix=[{"s": "-logy", "meaning": "study of"}],
    )
    html = entry_to_html(e)
    assert "-logy" in html


def test_prefix_as_list():
    """prefix 为 list → 渲染不崩溃。"""
    e = _full_entry()
    e.morpheme = Morpheme(
        roots=[{"root": "bio", "lang": "Greek", "meaning": "life"}],
        prefix=[{"p": "astro-", "meaning": "star"}],
        suffix=None,
    )
    html = entry_to_html(e)
    assert "astro-" in html


def test_morpheme_normal_dict():
    """正常 dict 结构 → 正常渲染。"""
    e = _full_entry()
    e.morpheme = Morpheme(
        roots=[{"root": "pheno", "lang": "Greek", "meaning": "appearance"}],
        prefix={"p": "pheno-", "meaning": "appearance"},
        suffix={"s": "-logy", "meaning": "study"},
    )
    html = entry_to_html(e)
    assert "pheno-" in html
    assert "-logy" in html


def test_batch_merge_suffix_list():
    """batch_llm 合并 suffix list → 不崩溃。"""
    from paeg_vocabulary.enrichers.batch_llm import _merge_to_entry
    e = VocabularyEntry(headword="test")
    _merge_to_entry(e, {"headword": "test",
                        "morpheme": {"roots": [{"root": "t", "lang": "L", "meaning": "m"}],
                                     "prefix": [{"p": "p-", "meaning": "pre"}],
                                     "suffix": [{"s": "-s", "meaning": "suf"}]}})
    assert e.morpheme is not None
    assert e.morpheme.prefix.get("p") == "p-"
    assert e.morpheme.suffix.get("s") == "-s"
