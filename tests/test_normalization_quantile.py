# -*- coding: utf-8 -*-
"""P2 ⭐ 归一化 × 分位联动测试（独立词条判定 → 分位 Q → 重要性信号）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.normalization import (
    should_preserve_form, decision_to_entry_key, is_important_decision,
    decision_quantile,
)


# ── R1: 决策 → 词条 key ──
def test_inflection_folds_to_lemma():
    """屈折（walked→walk）→ 折叠为 lemma。"""
    d = should_preserve_form("walked", "walk", "VERB", lemma_pos="VERB")
    assert decision_to_entry_key(d) == "walk"


def test_derivation_preserves_surface():
    """派生术语（abandonment）→ 保留 surface。"""
    d = should_preserve_form("abandonment", "abandon", "NOUN", lemma_pos="VERB")
    assert decision_to_entry_key(d) == "abandonment"


# ── R2: 重要性信号 ──
def test_book_term_is_important():
    """学术术语（定义句）→ is_important。"""
    d = should_preserve_form("phenomenon", "phenomenon", "NOUN",
                             lemma_pos="NOUN", ctx={"in_definition": True})
    assert is_important_decision(d) is True


def test_plain_word_not_important():
    """普通词无信号 → 非重要。"""
    d = should_preserve_form("table", "table", "NOUN", lemma_pos="NOUN")
    assert is_important_decision(d) is False


# ── R3: 分位联动 ──
def test_decision_quantile_range():
    """归一化决策词的分位在 0-1。"""
    d = should_preserve_form("walked", "walk", "VERB", lemma_pos="VERB")
    q = decision_quantile(d)
    assert 0.0 <= q <= 1.0


def test_decision_quantile_direction():
    """简单词（walk）分位低于难词（abandonment）。"""
    d1 = should_preserve_form("walked", "walk", "VERB", lemma_pos="VERB")
    d2 = should_preserve_form("abandonment", "abandon", "NOUN", lemma_pos="VERB")
    q1, q2 = decision_quantile(d1), decision_quantile(d2)
    assert q1 < q2, f"walk({q1:.3f}) 应比 abandonment({q2:.3f}) 简单"
