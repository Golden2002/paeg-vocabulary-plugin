# -*- coding: utf-8 -*-
"""P6 ⭐ 渲染层测试（FIELD_RENDERERS 注册表 + L1 完整性门）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.entry import VocabularyEntry
from paeg_vocabulary.render.field_renderers import (
    FIELD_RENDERERS, register_field, render_entry,
    validate_l1_complete, l1_missing_fields,
)
from paeg_vocabulary.render.entry_html import entry_to_html


# ── R1: FIELD_RENDERERS 注册机制 ──
def test_register_field():
    """自定义字段渲染器注册（生态可扩展）。"""
    assert "headword" in FIELD_RENDERERS
    assert "ipa" in FIELD_RENDERERS


def test_render_entry_headword():
    """headword 渲染器输出词头。"""
    e = VocabularyEntry(headword="life", pos="n.")
    html = render_entry("headword", e)
    assert "life" in html


def test_render_entry_missing_field():
    """未注册字段 → 抛错（防静默丢失）。"""
    e = VocabularyEntry(headword="life")
    with pytest.raises(KeyError):
        render_entry("nonexistent_field", e)


# ── R2: L1 完整性门 ──
def test_l1_missing_fields_empty_entry():
    """空条目缺全部 L1 字段。"""
    e = VocabularyEntry()
    missing = l1_missing_fields(e)
    assert "headword" in missing
    assert "ipa" in missing


def test_l1_missing_fields_complete_entry():
    """完整条目无缺失。"""
    e = VocabularyEntry(
        headword="life", pos="n.",
        ipa={"en_us": "/laɪf/"},
        gloss_bilingual={"zh": "生命", "en": "life"},
        examples=[{"en": "Life is beautiful.", "zh": "生命是美好的。"}],
        lemma="life",
    )
    assert l1_missing_fields(e) == []


def test_validate_l1_complete():
    """完整性校验布尔（examples 为 L2——释义+音标+词头即完整）。"""
    e = VocabularyEntry(headword="x")
    assert validate_l1_complete(e) is False
    e.ipa = {"en_us": "/x/"}
    assert validate_l1_complete(e) is False  # 仍缺 gloss
    e.gloss_bilingual = {"zh": "x", "en": "x"}
    assert validate_l1_complete(e) is True  # 无例句也完整（L2）


# ── R3: entry_to_html 完整渲染 ──
def test_entry_to_html_full():
    """完整条目 → HTML 含全部字段区块。"""
    e = VocabularyEntry(
        headword="phenomenology", pos="n.",
        ipa={"en_us": "/fɪˌnɒmɪˈnɒlədʒi/"},
        gloss_bilingual={"zh": "现象学", "en": "the study of consciousness"},
        etymology="from Greek phainomenon + logos",
        examples=[{"en": "Husserl founded phenomenology.", "zh": "胡塞尔创立了现象学。"}],
        collocations=["phenomenological method"],
        lemma="phenomenology",
    )
    html = entry_to_html(e)
    assert "phenomenology" in html
    assert "现象学" in html
    assert "/fɪˌnɒmɪˈnɒl" in html
    assert "Husserl" in html


def test_entry_to_html_incomplete_entry():
    """不完整条目 → 不渲染（L1 门拦截）→ 返回空。"""
    e = VocabularyEntry(headword="ghost")
    assert entry_to_html(e) == ""
