# -*- coding: utf-8 -*-
"""spaCy POS 词形还原测试（§3.116 ⭐ Round 7）：动名词/名词歧义消解。

背景：规则级兜底（_rule_lemmatize）用「频率信号 + stoplist」三层收敛，
但无法彻底消除动名词兼名词歧义——reading/feeling/drawing/writing/painting/cooking
既是动名词（VERB，应还原 base 动词 read/feel/...）又是独立名词（NOUN，应保持
reading/feeling/... 为独立词条）。本机默认 py3.14 无 cp314 轮子，spaCy 不可用，
故规则兜底路径由 test_lemmatize_fix.py 覆盖；本测试锁定 spaCy POS 感知路径的
正确行为，只在 spaCy + en_core_web_sm 可用时运行（否则跳过）。

验证方式（本机 py3.12 venv）：
    py -3.12 -m venv .venv-spacy312
    .venv-spacy312/Scripts/python -m pip install "spacy>=3.7" pytest
    .venv-spacy312/Scripts/python -m spacy download en_core_web_sm
    .venv-spacy312/Scripts/python -m pytest tests/test_spacy_pos.py -v
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

# spaCy 未安装时优雅跳过（规则级兜底由 test_lemmatize_fix.py 全量覆盖）
pytest.importorskip(
    "spacy", reason="spaCy 未安装；规则级兜底路径由 test_lemmatize_fix.py 覆盖")

from paeg_vocabulary.pipeline.clean_dedup import (  # noqa: E402
    _lemmatize_with_pos, _lemmatize_spacy, clean_corpus)
from paeg_vocabulary.core.context import VocabularyContext  # noqa: E402
from paeg_vocabulary.normalization import should_preserve_form  # noqa: E402


def _tagged(tokens):
    """token → {lemma, pos, lemma_pos} 映射（保持顺序 zip）。"""
    return {t: d for t, d in zip(tokens, _lemmatize_with_pos(tokens))}


def test_spacy_model_loads():
    import spacy
    nlp = spacy.load("en_core_web_sm")
    assert nlp is not None


def test_gerund_verb_reduces_to_base_verb():
    """动名词（VERB 上下文）→ 还原 base 动词（reading→read）。"""
    tagged = _tagged(["I", "am", "reading", "a", "book"])
    assert tagged["reading"]["lemma"] == "read"
    assert tagged["reading"]["pos"] == "VERB"


def test_gerund_noun_preserved_as_independent():
    """独立名词（NOUN 上下文）→ 保持原形（reading→reading，不折叠成 read）。

    §3.116 ⭐ Round 7：这正是规则兜底无法消除的歧义——「The reading was beautiful」
    里的 reading 是独立名词（a reading），spaCy POS 判定 NOUN 后 lemma=reading，
    经 should_preserve_form 不折叠回 read。
    """
    tagged = _tagged(["the", "reading", "of", "the", "book"])
    assert tagged["reading"]["lemma"] == "reading"
    assert tagged["reading"]["pos"] == "NOUN"


def test_irregular_third_person_singular():
    """不规则三单走 spaCy 正确还原（goes→go / does→do / has→have）。

    与规则兜底 _IRREGULAR_LEMMAS 一致（Round 6），spaCy 路径也应给出同样结果。
    """
    tagged = _tagged(["goes", "does", "has"])
    assert tagged["goes"]["lemma"] == "go"
    assert tagged["does"]["lemma"] == "do"
    assert tagged["has"]["lemma"] == "have"


def test_should_preserve_form_verb_reading_collapses():
    """动词 reading（VERB）→ 屈折变化 → 折叠到 read。"""
    d = should_preserve_form("reading", "read", "VERB", lemma_pos="VERB")
    assert d.is_lexically_independent is False
    assert d.lemma == "read"


def test_should_preserve_form_noun_reading_keeps_surface():
    """名词 reading（NOUN）→ 非屈折非派生 → 保持 surface（reading）。"""
    d = should_preserve_form("reading", "reading", "NOUN", lemma_pos="NOUN")
    assert d.is_lexically_independent is False
    assert d.lemma == "reading"


def test_clean_corpus_gerund_disambiguation_end_to_end():
    """端到端：动词 reading 折叠为 read，名词 reading 保留为独立词条。

    raw_corpus = "I am reading a book. The reading was beautiful."
    经 clean_corpus 后 clean_corpus 的 lemma 集合应同时含 read（动词折叠）
    与 reading（名词保留），而非全部折叠成 read（规则兜底的歧义）或全部保留。
    """
    ctx = VocabularyContext(
        target_lang="en",
        raw_corpus="I am reading a book. The reading was beautiful.")
    clean_corpus(ctx)
    lemmas = [ts.lemma for ts in ctx.clean_corpus]
    assert "read" in lemmas, f"动词 reading 应折叠为 read，得到 {lemmas}"
    assert "reading" in lemmas, f"名词 reading 应保留为独立词条，得到 {lemmas}"
    # 停用词（I/am/a/the/was）应被过滤
    assert "i" not in lemmas and "be" not in lemmas and "a" not in lemmas


def test_lemmatize_spacy_smoke():
    """_lemmatize_spacy（纯 lemma 列表）冒烟：三单/复数/动名词正确还原。"""
    out = _lemmatize_spacy(["goes", "books", "making", "running"])
    assert out == ["go", "book", "make", "run"]
