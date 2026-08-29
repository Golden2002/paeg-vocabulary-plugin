# -*- coding: utf-8 -*-
"""LLM 职责节点测试：本书关键术语判断 + 渲染前审查。"""
import pytest

from paeg_vocabulary.enrichers.book_term_gate import (
    judge_book_terms, fallback_must_keep,
)
from paeg_vocabulary.pipeline.review import review_entries


# ---------- book_term_gate ----------

def test_judge_book_terms_llm():
    def fake_chat(sys_p, usr_p):
        assert "关键术语" in sys_p
        return '{"must_keep": [{"word": "allele", "reason": "遗传学核心概念"}, {"word": "genotype", "reason": "核心术语"}]}'
    cands = [
        {"headword": "allele", "freq_count": 20, "contexts": ["..."]},
        {"headword": "genotype", "freq_count": 13, "contexts": ["..."]},
        {"headword": "the", "freq_count": 100, "contexts": ["..."]},
    ]
    mk = judge_book_terms("Population Genetics", cands, fake_chat)
    assert "allele" in mk
    assert "genotype" in mk
    assert "the" not in mk
    assert "遗传学核心概念" in mk["allele"][0]


def test_judge_book_terms_no_llm_returns_empty():
    def no_chat(sys_p, usr_p):
        return ""
    cands = [{"headword": "allele", "freq_count": 20}]
    assert judge_book_terms("Book", cands, no_chat) == {}


def test_judge_book_terms_no_candidates():
    def fake_chat(sys_p, usr_p):
        return "{}"
    assert judge_book_terms("Book", [], fake_chat) == {}


def test_fallback_must_keep_domain_and_freq():
    cands = [
        {"headword": "allele", "freq_count": 20, "global_zipf": 4.0},
        {"headword": "rareword", "freq_count": 1, "global_zipf": 2.0},
    ]
    mk = fallback_must_keep(cands, domain_terms={"allele"})
    assert "allele" in mk
    assert "rareword" not in mk


def test_fallback_high_freq_weak_keep():
    cands = [{"headword": "phenotype", "freq_count": 18, "global_zipf": 4.5}]
    mk = fallback_must_keep(cands)
    assert "phenotype" in mk


# ---------- review ----------

def test_review_fixes_fields():
    def fake_chat(sys_p, usr_p):
        assert "质检" in sys_p
        assert "用户需求" in usr_p
        return '{"fixes": [{"word": "phenomenon", "field": "gloss_bilingual.zh", "after": "现象", "action": "replace"}]}'
    entries = [{"headword": "phenomenon", "gloss_bilingual": {"en": "phenomenon", "zh": ""}}]
    out = review_entries(entries, fake_chat, user_context="水平 C1")
    assert out[0]["gloss_bilingual"]["zh"] == "现象"


def test_review_remove_action():
    def fake_chat(sys_p, usr_p):
        return '{"fixes": [{"word": "noise", "action": "remove"}]}'
    entries = [{"headword": "noise"}]
    out = review_entries(entries, fake_chat)
    assert out[0]["_removed"] is True


def test_review_no_llm_passthrough():
    def no_chat(sys_p, usr_p):
        return ""
    entries = [{"headword": "x", "gloss_bilingual": {"zh": "保留"}}]
    out = review_entries(entries, no_chat)
    assert out == entries  # 原样返回
