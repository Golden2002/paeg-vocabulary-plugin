# -*- coding: utf-8 -*-
"""P5 ⭐ LLM 批量补全测试（20 词/批 + JSON schema + 断点续跑）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.entry import VocabularyEntry
from paeg_vocabulary.enrichers.batch_llm import (
    chunk_words, batch_enrich, build_batch_prompt, parse_batch_response,
    enrich_with_batch, BATCH_SYSTEM_PROMPT,
)


# ── R1: 分批 ──
def test_chunk_words_size():
    """20 词/批分块。"""
    words = list(range(45))
    chunks = chunk_words(words, 20)
    assert [len(c) for c in chunks] == [20, 20, 5]


def test_chunk_words_empty():
    assert chunk_words([], 20) == []


# ── R2: 批量提示词 ──
def test_build_batch_prompt():
    """提示词含词列表 + 顺序要求 + schema 提示。"""
    prompt = build_batch_prompt(["life", "abandonment"])
    assert "life" in prompt and "abandonment" in prompt
    assert "headword" in prompt  # 防串味校验提示
    assert "JSON" in prompt or "json" in prompt


# ── R3: 响应解析（JSON 数组）──
def test_parse_batch_response_valid():
    """合法 JSON 数组 → 解析成功。"""
    raw = '[{"headword": "life", "pos": "n.", "gloss_zh": "生命"}, {"headword": "abandonment", "pos": "n.", "gloss_zh": "放弃"}]'
    entries = parse_batch_response(raw)
    assert len(entries) == 2
    assert entries[0]["headword"] == "life"


def test_parse_batch_response_invalid_json():
    """非法 JSON → 正则提取兜底。"""
    raw = 'prefix [{"headword": "life", "pos": "n.", "gloss_zh": "生命"}] suffix'
    entries = parse_batch_response(raw)
    assert len(entries) == 1
    assert entries[0]["headword"] == "life"


def test_parse_batch_response_garbage():
    """纯垃圾 → 空列表（不抛异常）。"""
    assert parse_batch_response("完全不是 JSON") == []


def test_parse_batch_response_headword_mismatch():
    """headword 与请求词不匹配 → 丢弃（防串味）。"""
    raw = '[{"headword": "different_word", "pos": "n.", "gloss_zh": "x"}]'
    entries = parse_batch_response(raw, expected={"life"})
    assert entries == []  # 不匹配丢弃


# ── R4: 端到端批量补全 ──
def test_batch_enrich_with_mock_llm():
    """mock LLM 批量补全——条目字段更新。"""
    entries = [VocabularyEntry(headword="life"), VocabularyEntry(headword="run")]

    def _mock_chat(sys_p, usr_p):
        return ('[{"headword": "life", "pos": "n.", "gloss_zh": "生命", "gloss_en": "life", '
                '"ipa": {"en_us": "/laɪf/"}}, '
                '{"headword": "run", "pos": "v.", "gloss_zh": "跑", "gloss_en": "run", '
                '"ipa": {"en_us": "/rʌn/"}}]')

    result = batch_enrich(entries, _mock_chat, batch_size=2)
    assert result[0].gloss_bilingual.get("zh") == "生命"
    assert result[1].gloss_bilingual.get("zh") == "跑"
    assert result[0].ipa.get("en_us") == "/laɪf/"


def test_batch_enrich_partial_failure():
    """部分批失败 → 不阻塞其他批（断点续跑基础）。"""
    entries = [VocabularyEntry(headword="a"), VocabularyEntry(headword="b"),
               VocabularyEntry(headword="c")]
    calls = {"n": 0}

    def _flaky_chat(sys_p, usr_p):
        calls["n"] += 1
        if calls["n"] == 1:
            return ""  # 第一批失败
        return '[{"headword": "c", "pos": "n.", "gloss_zh": "c词"}]'

    result = batch_enrich(entries, _flaky_chat, batch_size=2)
    # 第二批成功 → c 有释义；a/b 失败保留原样
    assert result[2].gloss_bilingual.get("zh") == "c词"
    assert result[0].gloss_bilingual == {}


# ── R5: 全字段在线补全（§3.116 ⭐ CEFR 等级字段补齐）──
def test_batch_schema_has_all_fields():
    """批量补全 schema 覆盖词源/词素/多义项/例句/搭配/CEFR 全字段。"""
    for field in ("etymology", "morpheme", "senses", "examples",
                  "collocations", "cefr_level", "book_sense"):
        assert field in BATCH_SYSTEM_PROMPT


def test_batch_enrich_cefr_level():
    """LLM 返回 cefr_level → 合并到条目。"""
    entries = [VocabularyEntry(headword="abandonment")]

    def _mock_chat(sys_p, usr_p):
        return '[{"headword": "abandonment", "pos": "n.", "cefr_level": "C1"}]'

    result = batch_enrich(entries, _mock_chat, batch_size=1)
    assert result[0].cefr_level == "C1"
