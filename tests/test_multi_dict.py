# -*- coding: utf-8 -*-
"""多词典查询 + 义项合并去重 + 来源标注测试（§3.116 ⭐）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.multi_dict import (
    MultiDict, WordNetSource, merge_senses, _normalize_sense, _near_identical,
)


# ── R1: 义项归一化 ──
def test_normalize_sense_strips_pos_and_brackets():
    norm, tokens = _normalize_sense("n. 商标\n[法] trademark")
    assert norm.startswith("trademark") or "trademark" in norm
    assert "n." not in norm  # 词性前缀已去


def test_normalize_sense_empty():
    assert _normalize_sense("") == ("", set())


# ── R2: 完全一致义项合并（跨词典去重）──
def test_merge_identical_senses_across_sources():
    items = [
        {"text": "an observable event", "source": "ecdict", "lang": "en"},
        {"text": "an observable event", "source": "wordnet", "lang": "en"},
        {"text": "an observable event", "source": "kaikki", "lang": "en"},
    ]
    en, zh = merge_senses(items)
    assert len(en) == 1
    assert set(en[0]["sources"]) == {"ecdict", "wordnet", "kaikki"}
    assert zh == []


# ── R3: 近似义项合并（子串/高重叠）──
def test_merge_near_identical_senses():
    items = [
        {"text": "a natural phenomenon", "source": "ecdict", "lang": "en"},
        {"text": "a natural phenomenon that is observable", "source": "wordnet", "lang": "en"},
    ]
    en, _ = merge_senses(items)
    assert len(en) == 1
    # 保留更长文本
    assert "observable" in en[0]["text"]
    assert set(en[0]["sources"]) == {"ecdict", "wordnet"}


def test_merge_keeps_distinct_senses():
    items = [
        {"text": "an observable event", "source": "ecdict", "lang": "en"},
        {"text": "a unit of biological heredity", "source": "wordnet", "lang": "en"},
    ]
    en, _ = merge_senses(items)
    assert len(en) == 2  # 两个不同义项不合并


# ── R4: 中文义项分列合并 ──
def test_merge_zh_senses_separate():
    items = [
        {"text": "现象", "source": "ecdict", "lang": "zh"},
        {"text": "现象", "source": "ecdict", "lang": "zh"},
        {"text": "an event", "source": "wordnet", "lang": "en"},
    ]
    en, zh = merge_senses(items)
    assert len(en) == 1
    assert len(zh) == 1
    assert zh[0]["sources"] == ["ecdict"]


# ── R5: WordNet 源无 nltk 时优雅降级 ──
def test_wordnet_source_degrades_without_nltk():
    src = WordNetSource()
    defs = src.definitions("nonexistent_zzz")
    assert isinstance(defs, list)  # 不抛异常


# ── R6: MultiDict 综合查询（真实离线数据）──
def test_multidict_query_phenomenon():
    md = MultiDict()
    r = md.query("phenomenon")
    assert r["word"] == "phenomenon"
    assert r["senses_en"], "应有英文义项"
    assert r["senses_zh"], "应有 ECDICT 中文义项"
    # 来源标注：至少一条英文义项有 source
    assert all(s["sources"] for s in r["senses_en"])
    assert all(s["sources"] for s in r["senses_zh"])


def test_multidict_query_sources_attributed():
    md = MultiDict()
    r = md.query("ability")
    # ability 在 CEFR 词表 → cefr 来源出现在英文义项中
    srcs = [s for s in r["senses_en"] for s in s["sources"]]
    assert "cefr" in srcs
    assert r["cefr"] == "B1"


def test_multidict_query_unknown_word():
    md = MultiDict()
    r = md.query("zzzqqq_nonexistent_xyz_12345")
    assert r["word"] == "zzzqqq_nonexistent_xyz_12345"
    assert r["senses_en"] == []
    assert r["senses_zh"] == []


# ── R7: merge_senses 幂等（重复来源不重复累计）──
def test_merge_sources_no_duplicate():
    items = [
        {"text": "an observable event", "source": "ecdict", "lang": "en"},
        {"text": "an observable event", "source": "ecdict", "lang": "en"},
    ]
    en, _ = merge_senses(items)
    assert en[0]["sources"] == ["ecdict"]
