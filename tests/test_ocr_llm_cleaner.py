# -*- coding: utf-8 -*-
"""OCR 词库清理（LLM 判别）测试：确定性打标 + LLM 判别 + 修复/剔除 + 降级。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.context import TokenSpan, VocabularyContext
from paeg_vocabulary.enrichers.ocr_llm_cleaner import (
    OCR_CLEAN_SYSTEM_PROMPT, _known_word, collect_suspects,
    parse_clean_response, llm_classify, apply_llm_clean, build_clean_prompt,
)


# ── R1: 确定性打标（离线词典认识与否）──
def test_known_word_true():
    assert _known_word("science") is True


def test_known_word_false():
    assert _known_word("scienc") is False  # 词尾丢失畸形词
    assert _known_word("zzqqxx_nonexistent") is False


# ── R2: 响应解析 ──
def test_parse_clean_response():
    raw = ('{"decisions": ['
           '{"word": "scienc", "action": "repair", "replacement": "science", "reason": "e 丢失"},'
           '{"word": "plath", "action": "proper", "replacement": "", "reason": "人名"},'
           '{"word": "gggg", "action": "noise", "replacement": "", "reason": "重复字符"}]}')
    d = parse_clean_response(raw)
    assert d["scienc"]["action"] == "repair"
    assert d["scienc"]["replacement"] == "science"
    assert d["plath"]["action"] == "proper"
    assert d["gggg"]["action"] == "noise"


def test_parse_clean_response_garbage():
    assert parse_clean_response("不是 JSON") == {}
    assert parse_clean_response("") == {}


def test_parse_clean_response_invalid_action_defaults_keep():
    raw = '{"decisions": [{"word": "abc", "action": "weird", "replacement": ""}]}'
    d = parse_clean_response(raw)
    assert d["abc"]["action"] == "keep"


# ── R3: 提示词含确定性数据 ──
def test_build_clean_prompt():
    p = build_clean_prompt([{"word": "scienc", "freq": 3, "cap_ratio": 0.0}])
    assert "scienc" in p and "3" in p


# ── R4: collect_suspects 只挑词典外词 ──
def test_collect_suspects():
    ctx = VocabularyContext()
    ctx.clean_corpus = [
        TokenSpan(token="science", lemma="science"),
        TokenSpan(token="scienc", lemma="scienc"),
        TokenSpan(token="scienc", lemma="scienc"),
        TokenSpan(token="zzqqxx", lemma="zzqqxx"),
    ]
    s = collect_suspects(ctx)
    words = {x["word"] for x in s}
    assert "scienc" in words and "zzqqxx" in words
    assert "science" not in words  # 词典认识 → 非嫌疑


# ── R5: apply_llm_clean 修复 + 剔除 ──
def test_apply_llm_clean_repair_and_drop():
    ctx = VocabularyContext()
    ctx.clean_corpus = [
        TokenSpan(token="scienc", lemma="scienc"),
        TokenSpan(token="scienc", lemma="scienc"),
        TokenSpan(token="plath", lemma="plath"),
        TokenSpan(token="gggg", lemma="gggg"),
        TokenSpan(token="science", lemma="science"),
    ]

    def fake_chat(sys_p, usr_p):
        assert "OCR" in sys_p or "清理" in sys_p
        return ('{"decisions": ['
                '{"word": "scienc", "action": "repair", "replacement": "science"},'
                '{"word": "plath", "action": "proper", "replacement": ""},'
                '{"word": "gggg", "action": "noise", "replacement": ""}]}')

    ctx = apply_llm_clean(ctx, chat_fn=fake_chat)
    lemmas = [t.lemma for t in ctx.clean_corpus]
    assert "science" in lemmas          # scienc 已修复为 science
    assert "scienc" not in lemmas
    assert "plath" not in lemmas        # 专名剔除
    assert "gggg" not in lemmas         # 噪声剔除
    assert ctx.llm_ocr_clean["repaired"] == ["scienc"]
    assert set(ctx.llm_ocr_clean["dropped"]) == {"plath", "gggg"}


# ── R6: 降级（无 chat_fn / LLM 空响应 / 异常）──
def test_apply_llm_clean_no_chat_fn():
    ctx = VocabularyContext()
    ctx.clean_corpus = [TokenSpan(token="scienc", lemma="scienc")]
    ctx2 = apply_llm_clean(ctx, chat_fn=None)
    assert ctx2.clean_corpus == ctx.clean_corpus  # 原样返回


def test_apply_llm_clean_empty_llm():
    ctx = VocabularyContext()
    ctx.clean_corpus = [TokenSpan(token="scienc", lemma="scienc")]

    def empty_chat(sys_p, usr_p):
        return ""

    ctx = apply_llm_clean(ctx, chat_fn=empty_chat)
    assert [t.lemma for t in ctx.clean_corpus] == ["scienc"]  # 未改动


def test_llm_classify_partial_failure():
    suspects = [{"word": "scienc", "freq": 2, "cap_ratio": 0.0},
                {"word": "zzqqxx", "freq": 1, "cap_ratio": 0.0}]
    calls = {"n": 0}

    def flaky(sys_p, usr_p):
        calls["n"] += 1
        if calls["n"] == 1:
            return ""  # 第一批失败
        return '{"decisions": [{"word": "zzqqxx", "action": "noise", "replacement": ""}]}'

    d = llm_classify(suspects, flaky, batch_size=1)
    assert d["zzqqxx"]["action"] == "noise"
    assert "scienc" not in d  # 失败批不产出
