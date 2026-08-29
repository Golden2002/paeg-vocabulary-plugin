# -*- coding: utf-8 -*-
"""词库扩充测试：ECDICT 全列 / kaikki 词源接线 / 中英双释义。"""
import pytest

from paeg_vocabulary.wordbank import WordBank, EcdictSource


@pytest.fixture(scope="module")
def wb():
    return WordBank()


def test_ecdict_source_full_columns():
    src = EcdictSource()
    r = src.lookup("phenomenon")
    assert r is not None
    assert r["translation_zh"]  # 中文释义
    assert r["definition_en"]  # 英文释义
    assert r["pos"]  # 词性


def test_wordbank_gloss_zh_from_ecdict(wb):
    r = wb.lookup("phenomenon")
    assert r["gloss_zh"], "ECDICT 中文释义未接线"
    assert "现象" in r["gloss_zh"]


def test_wordbank_gloss_en_fallback(wb):
    r = wb.lookup("phenomenon")
    assert r["gloss_en"], "英文释义兜底链（CEFR→kaikki→ECDICT）未生效"


def test_wordbank_etymology_from_kaikki(wb):
    r = wb.lookup("phenomenon")
    assert r["etymology"], "kaikki 词源未接线"
    assert "ancient greek" in r["etymology"].lower() or "greek" in r["etymology"].lower()


def test_wordbank_genetics_etymology(wb):
    r = wb.lookup("genotype")
    assert r["etymology"] or r["domain_term"], "遗传学词条应有词源或领域标注"


def test_coverage_includes_ecdict(wb):
    stats = wb.coverage_stats()
    assert stats.get("ecdict_words", 0) > 100000
