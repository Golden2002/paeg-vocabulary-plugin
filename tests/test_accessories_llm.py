# -*- coding: utf-8 -*-
"""附件 LLM 增强测试：智能学习解读 + 趣味语言解读（§3.120 ⭐）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.entry import CandidateWord, VocabularyEntry
from paeg_vocabulary.core.context import VocabularyContext
from paeg_vocabulary.accessories import (
    llm_analysis, llm_fun_insights, generate_all_accessories,
)


def _make_ctx():
    ctx = VocabularyContext(pdf_path="sample_book.pdf")
    ctx.entries = [
        VocabularyEntry(headword="phenomenon", pos="n.", cefr_level="B2",
                        etymology="From Greek phainomenon"),
        VocabularyEntry(headword="gene", pos="n.", cefr_level="C1",
                        etymology="From Greek genos (origin)"),
    ]
    ctx.candidates = [
        CandidateWord(headword="phenomenon", freq_count=20, cefr_guess="B2"),
        CandidateWord(headword="gene", freq_count=12, cefr_guess="C1"),
    ]
    return ctx


def test_llm_fun_insights_returns_markdown():
    ctx = _make_ctx()

    def fake_chat(sys_p, usr_p):
        assert "趣味" in sys_p
        assert "phenomenon" in usr_p  # 确定性数据已注入
        return "## 1. 本书关键术语「为什么重要」\n- phenomenon 是核心\n## 3. 同源词族\n- gene/genetic"

    out = llm_fun_insights(ctx, fake_chat)
    assert "本书关键术语" in out
    assert "同源词族" in out


def test_llm_fun_insights_no_llm_returns_empty():
    ctx = _make_ctx()
    assert llm_fun_insights(ctx, chat_fn=lambda s, u: "") == ""


def test_llm_analysis_still_works():
    ctx = _make_ctx()

    def fake_chat(sys_p, usr_p):
        assert "分析" in sys_p
        return "## 1. 高频词解读\n- 内容"

    out = llm_analysis(ctx, fake_chat)
    assert "高频词解读" in out


def test_generate_all_accessories_includes_fun(tmp_path):
    ctx = _make_ctx()

    def fake_chat(sys_p, usr_p):
        if "趣味" in sys_p:
            return "## 1. 本书关键术语「为什么重要」\n- 内容"
        if "分析" in sys_p:
            return "## 1. 高频词解读\n- 内容"
        return ""

    res = generate_all_accessories(ctx, out_dir=str(tmp_path), chat_fn=fake_chat)
    assert "智能学习解读.md" in res
    assert "趣味语言解读.md" in res
    assert ctx.llm_fun  # 存回 ctx 供交互页复用


def test_generate_all_accessories_no_llm_no_fun(tmp_path):
    ctx = _make_ctx()
    res = generate_all_accessories(ctx, out_dir=str(tmp_path), chat_fn=lambda s, u: "")
    assert "趣味语言解读.md" not in res  # 无 LLM 不产出趣味附件，但其余附件正常
    assert "词频统计报告.md" in res


def test_interactive_render_includes_fun_tab(tmp_path):
    """交互式交付页新增「趣味解读」标签页（§3.120 ⭐）。"""
    from paeg_vocabulary.render.interactive import render_interactive_html
    ctx = _make_ctx()
    ctx.entries = [VocabularyEntry(headword="phenomenon", pos="n.",
                                   ipa={"en_us": "/x/"}, gloss_bilingual={"zh": "现象", "en": "p"},
                                   cefr_level="B2")]
    p = render_interactive_html(ctx, out_dir=str(tmp_path), book_title="T",
                                llm_analysis="## 解读", fun_insights="## 趣味")
    assert p is not None
    html = open(p, encoding="utf-8").read()
    assert "趣味解读" in html
    assert 'id="fun"' in html
