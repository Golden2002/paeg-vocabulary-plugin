# -*- coding: utf-8 -*-
"""P5 ⭐ 本地专业词库测试（离线音标/释义/分级 + 多词库冲突整合消歧）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.wordbank import (
    WordBank, CmuIpaSource, CefrGlossSource, OxfordLevelSource,
    resolve_ipa_conflict, resolve_gloss_conflict, resolve_level_conflict,
)


# ── R1: CMU 音标离线查询 ──
def test_cmu_ipa_lookup():
    """CMU dict 离线查询常见词音标。"""
    src = CmuIpaSource()
    ipa = src.lookup("life")
    assert ipa, "life 应有 CMU 音标"
    assert "/" in ipa  # IPA 格式


def test_cmu_ipa_unknown():
    """CMU 无此词 → None。"""
    src = CmuIpaSource()
    assert src.lookup("zzzqqq_nonexistent_xyz") is None


# ── R2: CEFR 释义离线查询 ──
def test_cefr_gloss_lookup():
    """CEFR 词表离线查询释义 + 等级。"""
    src = CefrGlossSource()
    r = src.lookup("ability")
    assert r is not None
    assert r.get("gloss_en"), "应有英文释义"
    assert r.get("cefr") == "B1"


# ── R3: Oxford 3000 分级 ──
def test_oxford_level_lookup():
    """Oxford 3000 分级查询。"""
    src = OxfordLevelSource()
    lv = src.lookup("the")
    assert lv == "A1"


# ── R4: 多词库冲突整合（音标）──
def test_resolve_ipa_conflict():
    """CMU 与 espeak 冲突 → 以 CMU 为准（权威源优先）。"""
    cmu = "/laɪf/"
    espeak = "/laɪf/ (different)"
    resolved = resolve_ipa_conflict({"cmu": cmu, "espeak": espeak}, primary="cmu")
    assert resolved == cmu


# ── R5: 多词库冲突整合（释义/等级）──
def test_resolve_gloss_conflict():
    """CEFR 词表 vs LLM 释义冲突 → 策略合并（词表优先基础义，LLM 补本书义）。"""
    resolved = resolve_gloss_conflict(
        bank_gloss="the power or skill to do something",
        llm_gloss="能力",
        strategy="bank_first")
    assert "power" in resolved


def test_resolve_level_conflict():
    """Oxford vs CEFR-J vs LLM 等级冲突 → 取最难（保守学习）。"""
    lv = resolve_level_conflict({"oxford": "B1", "cefrj": "B2", "llm": "A2"},
                                strategy="hardest")
    assert lv == "B2"


# ── R6: WordBank 统一入口 ──
def test_wordbank_lookup():
    """WordBank 综合查询（音标+释义+等级+冲突消歧）。"""
    wb = WordBank()
    r = wb.lookup("ability")
    assert r["ipa"], "应有音标"
    assert r["gloss_en"], "应有释义"
    assert r["cefr"], "应有等级"
    assert "sources" in r  # 来源追踪


def test_wordbank_unknown_word():
    """未知词 → 兜底（返回空但可用 LLM 补全）。"""
    wb = WordBank()
    r = wb.lookup("zzzqqq_nonexistent_xyz_12345")
    assert r is not None  # 返回结构而非抛异常


# ── R7: 学科术语辞典（kaikki 真实数据）──
def test_domain_glossary_philosophy():
    """现象学/哲学术语（phenomenon 在 philosophy topic）。"""
    wb = WordBank(domains=["philosophy", "phenomenology"])
    r = wb.lookup("phenomenology")
    assert r["domain_term"] is not None, "phenomenology 应在哲学/现象学辞典"
    assert r["domain_term"].get("gloss_en"), "应有英文定义"


def test_domain_glossary_biology():
    """分子生物学术语（cell/gene/protein 在 biology topic）。"""
    wb = WordBank(domains=["biology", "biochemistry", "genetics"])
    r = wb.lookup("protein")
    assert r["domain_term"] is not None, "protein 应在生物学辞典"
    assert r["domain_term"].get("gloss_en"), "应有英文定义"


def test_domain_glossary_coverage():
    """学科辞典覆盖统计（真实数据量）。"""
    wb = WordBank(domains=["philosophy"])
    assert wb.coverage_stats()["domain_terms"] > 1000, "哲学辞典应加载 1000+ 术语"
