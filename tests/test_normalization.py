# -*- coding: utf-8 -*-
"""词形归一化策略测试（§3.116 ⭐：屈折归一化 vs 派生保留）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.normalization import should_preserve_form


# ─────────────────────────────────────
# 1. 屈折归一化（POS 不变 → 安全归一化）
# ─────────────────────────────────────
class TestInflectionalNormalize:
    def test_past_tense_normalized(self):
        """walked → walk（屈折，POS 不变 → 归一化）。"""
        d = should_preserve_form("walked", "walk", "VERB", lemma_pos="VERB")
        assert d.is_lexically_independent is False

    def test_gerund_normalized(self):
        """running → run（屈折，POS 不变 → 归一化）。"""
        d = should_preserve_form("running", "run", "VERB", lemma_pos="VERB")
        assert d.is_lexically_independent is False

    def test_plural_normalized(self):
        """books → book（复数，归一化）。"""
        d = should_preserve_form("books", "book", "NOUN", lemma_pos="NOUN")
        assert d.is_lexically_independent is False


# ─────────────────────────────────────
# 2. 派生保留原形（POS 改变/后缀 → 独立词条）
# ─────────────────────────────────────
class TestDerivationalPreserve:
    def test_abandonment_preserved(self):
        """abandonment（海德格尔术语）→ 保留原形（派生 VERB→NOUN）。"""
        d = should_preserve_form("abandonment", "abandon", "NOUN", lemma_pos="VERB")
        assert d.is_lexically_independent is True
        assert d.surface == "abandonment"

    def test_nominalization_preserved(self):
        """异化/升华类 -tion/-ation 名词化 → 保留。"""
        d = should_preserve_form("alienation", "alienate", "NOUN", lemma_pos="VERB")
        assert d.is_lexically_independent is True

    def test_suffix_alone_preserved(self):
        """带派生后缀（无 POS 信息时也保留）——-ment。"""
        d = should_preserve_form("movement", "move", "NOUN", lemma_pos=None)
        assert d.is_lexically_independent is True


# ─────────────────────────────────────
# 3. 学术术语促进（与归一化解耦）
# ─────────────────────────────────────
class TestTermPromotion:
    def test_definition_context_promotes(self):
        """定义句中的词 → 标记术语。"""
        d = should_preserve_form("phenomenon", "phenomenon", "NOUN",
                                 lemma_pos="NOUN",
                                 ctx={"in_definition": True})
        assert d.is_book_term is True
        assert "定义句" in d.term_evidence

    def test_high_freq_promotes(self):
        """高频（≥5）→ 标记术语。"""
        d = should_preserve_form("consciousness", "consciousness", "NOUN",
                                 lemma_pos="NOUN", ctx={"freq": 8})
        assert d.is_book_term is True

    def test_term_promotes_surface(self):
        """屈折词但命中术语信号 → 表面形保留为术语。"""
        d = should_preserve_form("beings", "being", "NOUN",
                                 lemma_pos="NOUN",
                                 ctx={"in_heading": True})
        assert d.is_lexically_independent is True  # 术语促进提升
        assert d.is_book_term is True

    def test_normal_word_no_term(self):
        """普通词：归一化且非术语。"""
        d = should_preserve_form("simple", "simple", "ADJ", lemma_pos="ADJ")
        assert d.is_lexically_independent is False
        assert d.is_book_term is False


# ─────────────────────────────────────
# 4. 避免狭隘处理（通用性）
# ─────────────────────────────────────
class TestGenerality:
    def test_no_word_list(self):
        """策略由规则驱动——无特定词表（abandonment 靠派生规则命中）。"""
        # 同类派生词都保留（非只 abandonment）
        for w, lem in [("abandonment", "abandon"), ("alienation", "alienate"),
                       ("sublimation", "sublimate"), ("movement", "move")]:
            d = should_preserve_form(w, lem, "NOUN", lemma_pos="VERB")
            assert d.is_lexically_independent is True, f"{w} 应保留"

    def test_irregular_past_normalized(self):
        """不规则过去式（meant→mean）仍归一化（POS 不变）。"""
        d = should_preserve_form("meant", "mean", "VERB", lemma_pos="VERB")
        assert d.is_lexically_independent is False

    def test_decision_explainable(self):
        """决策可解释（reason 字段）。"""
        d = should_preserve_form("abandonment", "abandon", "NOUN", lemma_pos="VERB")
        assert d.reason != ""
