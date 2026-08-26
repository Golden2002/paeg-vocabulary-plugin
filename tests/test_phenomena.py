# -*- coding: utf-8 -*-
"""§3.116 ⭐ 语言现象识别测试（熟词生义/固定搭配/俚语——筛选豁免 + 条目标注 + 渲染）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest

from paeg_vocabulary.enrichers.idiom_enricher import (
    detect_polysemy, detect_collocation, detect_slang, detect_phenomena,
    is_important_phenomenon,
)
from paeg_vocabulary.core.entry import VocabularyEntry, CandidateWord
from paeg_vocabulary.pipeline.filter import filter_candidates
from paeg_vocabulary.core.context import VocabularyContext


# ── R1: 熟词生义检测 ──
def test_detect_polysemy_known_word():
    """熟词生义：spring（弹簧/泉水≠春天）应检测。"""
    assert detect_polysemy("spring") is not None
    assert "熟词生义" in detect_polysemy("spring")


def test_detect_polysemy_unknown_word():
    """普通词不误报。"""
    assert detect_polysemy("photosynthesis") is None
    assert detect_polysemy("") is None


# ── R2: 固定搭配检测 ──
def test_detect_collocation_hit():
    """固定搭配：文本含 break down 应检出。"""
    assert "break down" in detect_collocation("The machine will break down soon.")


def test_detect_collocation_miss():
    """无搭配文本返回空。"""
    assert detect_collocation("ordinary sentence here") == []


# ── R3: 俚语检测 ──
def test_detect_slang_hit():
    """俚语：once in a blue moon 应检出。"""
    assert "once in a blue moon" in detect_slang("He visits once in a blue moon.")


def test_detect_slang_miss():
    assert detect_slang("plain text") == []


# ── R4: 综合检测 ──
def test_detect_phenomena_structure():
    """综合检测返回三类键。"""
    p = detect_phenomena("spring", "The spring broke the machine.")
    assert set(p.keys()) == {"polysemy", "collocations", "slang"}


def test_is_important_phenomenon():
    """语言现象 = 重要信号。"""
    assert is_important_phenomenon("spring", "The spring broke.") is True
    assert is_important_phenomenon("photosynthesis", "plain text") is False


# ── R5: 筛选豁免（zipf 不达标但语言现象 → 保留）──
def test_filter_phenomenon_exemption():
    """语言现象豁免：spring（熟词生义）即使 zipf 低也保留。"""
    ctx = VocabularyContext(pdf_path="t.pdf", target_lang="en")
    # clean_corpus 简化：直接用 Token 对象（filter 内部只读 .lemma）
    class T:
        def __init__(self, w):
            self.lemma = w
            self.text = w
            self.pos = "NOUN"
    ctx.clean_corpus = [
        T("spring"), T("spring"), T("spring"),
        T("photosynthesis"), T("photosynthesis"), T("photosynthesis"),
    ]
    # 高 zipf 阈值（4.5）——photosynthesis 若 zipf 达标会保留；spring 靠豁免
    # 手动构造：zipf 均低 → 默认策略全滤除，仅豁免保留 spring
    ctx = filter_candidates(ctx, zipf_threshold=9.9)  # 极高阈值 → 全滤除
    kept = {c.headword for c in ctx.candidates}
    assert "spring" in kept, "熟词生义词应被豁免保留"
    # photosynthesis 无语言现象 + zipf 不达标 → 滤除
    assert "photosynthesis" not in kept


# ── R6: 条目 phenomena 字段 + 渲染 ──
def test_entry_phenomena_field():
    """enrich 阶段写入 entry.phenomena。"""
    from paeg_vocabulary.pipeline.enrich import enrich_entries
    cand = CandidateWord(headword="spring", lemma="spring", freq_count=3,
                         contexts=["The spring broke the machine."])
    ctx = VocabularyContext(pdf_path="t.pdf", target_lang="en")
    ctx.candidates = [cand]
    ctx = enrich_entries(ctx, chat_fn=None)  # 无 LLM——仅确定性补全
    assert ctx.entries[0].phenomena.get("polysemy"), "spring 应标注熟词生义"


def test_render_phenomena_html():
    """渲染：phenomena 输出 <span class="phen-tag">。"""
    from paeg_vocabulary.pipeline.render_html import _build_entry_html
    entry = VocabularyEntry(headword="spring", pos="n.",
                            phenomena={"polysemy": ["熟词生义：..."],
                                       "slang": [], "collocations": []})
    html = _build_entry_html(entry)
    assert "phen-tag" in html
    assert "熟词生义" in html


def test_render_no_phenomena_no_tag():
    """无现象不输出 phen-tag。"""
    from paeg_vocabulary.pipeline.render_html import _build_entry_html
    entry = VocabularyEntry(headword="photosynthesis", pos="n.",
                            phenomena={})
    html = _build_entry_html(entry)
    assert "phen-tag" not in html
