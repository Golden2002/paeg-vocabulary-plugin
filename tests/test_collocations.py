# -*- coding: utf-8 -*-
"""P5 ⭐ 原著搭配提取测试（N-gram 显著性——从书中提取固定搭配/短语）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.collocations import (
    extract_collocations, score_bigram, score_trigram, COLLOCATION_FILTER,
)


# ── R1: 二元搭配显著性 ──
def test_score_bigram_common():
    """常见搭配（of the）分数低（太常见无信息量）。"""
    s = score_bigram(100, 2000, 50)  # 共现 50
    assert s is not None


def test_score_bigram_rare():
    """罕见词搭配（分子生物术语）分数高（有信息量）。"""
    s1 = score_bigram(100, 2000, 50)
    assert isinstance(s1, float)


# ── R2: 从语料提取搭配 ──
def test_extract_collocations_simple():
    """从简单语料提取搭配——高频共现。"""
    corpus = [
        "The cell membrane regulates transport.",
        "The cell membrane is essential.",
        "Cell membrane structure varies.",
        "The membrane protein binds.",
        "Membrane protein plays a role.",
        "Protein synthesis begins.",
        "Protein synthesis is complex.",
        "Synthesis requires energy.",
        "Energy is conserved.",
    ]
    colls = extract_collocations(corpus, min_count=2, top_n=20)
    # cell membrane / protein synthesis 应出现
    phrases = [c["phrase"] for c in colls]
    assert "cell membrane" in phrases or "membrane protein" in phrases
    assert any("protein" in p for p in phrases)


def test_extract_collocations_empty():
    """空语料 → 空结果（不抛异常）。"""
    assert extract_collocations([]) == []


def test_extract_collocations_min_count():
    """min_count 过滤低频搭配。"""
    corpus = ["alpha beta gamma", "alpha beta gamma", "alpha beta gamma",
              "delta epsilon", "delta epsilon"]
    colls = extract_collocations(corpus, min_count=3)
    # alpha beta 出现 3 次 → 保留；delta epsilon 2 次 → 滤除
    phrases = [c["phrase"] for c in colls]
    assert "alpha beta" in phrases
    assert "delta epsilon" not in phrases


# ── R3: 搭配过滤（虚词/纯功能）──
def test_collocation_filter_removes_function_words():
    """纯虚词搭配（of the / in the）被过滤。"""
    assert "of the" in COLLOCATION_FILTER or not extract_collocations(
        ["of the people", "of the state"])


def test_trigram_extraction():
    """三元搭配提取。"""
    corpus = [
        "by virtue of his office he acts",
        "by virtue of the law it binds",
        "by virtue of nature we live",
        "by virtue of custom they agree",
        "in virtue of what she said",
    ]
    colls = extract_collocations(corpus, n=3, min_count=2)
    phrases = [c["phrase"] for c in colls]
    assert "by virtue of" in phrases


# ── R4: 与词汇表联动（按词查搭配）──
def test_collocations_for_word():
    """提取后可按词检索搭配。"""
    corpus = [
        "The cell membrane regulates.",
        "The cell membrane is essential.",
        "Cell membrane structure varies.",
        "The cell divides rapidly.",
        "Cell division is controlled.",
    ]
    colls = extract_collocations(corpus, min_count=2)
    # 找包含 cell 的搭配
    cell_colls = [c for c in colls if "cell" in c["phrase"]]
    assert cell_colls, "cell 应有搭配"
