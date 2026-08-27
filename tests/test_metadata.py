# -*- coding: utf-8 -*-
"""§3.116 ⭐ 书籍元数据 LLM 判定测试（文件名拦截启发式 + 重试 + 用户优先）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest

from paeg_vocabulary.metadata import (
    _looks_like_filename, _extract_book_meta_fallback, extract_book_meta_llm,
)


# ── R1: 文件名特征拦截 ──
def test_looks_like_filename_archive():
    """安娜档案文件名被拦截。"""
    assert _looks_like_filename("[Critical_insights]_Plath_..._libgen.li") is True
    assert _looks_like_filename("The phenomenon of life -- Jonas -- Anna's Archive") is True


def test_looks_like_filename_clean():
    """干净书名不拦截。"""
    assert _looks_like_filename("The Bell Jar") is False
    assert _looks_like_filename("The Phenomenon of Life") is False


def test_looks_like_filename_year_publisher():
    """含年份出版社的疑似文件名被拦截。"""
    assert _looks_like_filename("The bell jar, by Sylvia Plath (2012, Salem Press)") is True


# ── R2: 用户提供优先 ──
def test_user_provided_wins():
    """用户显式提供书名 → 直接返回（不调 LLM）。"""
    t, a = extract_book_meta_llm("whatever.pdf", chat_fn=None,
                                 user_filter={"book_title": "生命现象学", "book_author": "约纳斯"})
    assert t == "生命现象学"
    assert a == "约纳斯"


# ── R3: LLM 判定 + 文件名拦截重试 ──
def test_llm_judgement_with_retry(monkeypatch):
    """LLM 首次输出文件名 → 拦截重试 → 正确书名。"""
    from paeg_vocabulary import metadata as _md
    # mock 前 15 页提取（无需真实 PDF）
    monkeypatch.setattr(_md, "_extract_first_pages",
                        lambda p, n=15: "【第 1 页】\nTHE Phenomenon of Life  by Hans Jonas")
    calls = {"n": 0}

    def _chat(sys_p, usr_p):
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"book_title": "The phenomenon of life -- Anna\'s Archive", "book_author": ""}'
        return '{"book_title": "The Phenomenon of Life", "book_author": "Hans Jonas"}'

    t, a = extract_book_meta_llm(r"D:\fake\The phenomenon of life.pdf",
                                 chat_fn=_chat, user_filter={})
    assert calls["n"] >= 2, "应触发重试"
    assert t == "The Phenomenon of Life"
    assert a == "Hans Jonas"


# ── R4: 文件名兜底（LLM 不可用）──
def test_fallback_when_no_llm():
    """无 LLM → 文件名兜底（剥扩展名 + 来源后缀）。"""
    t, a = extract_book_meta_llm(r"D:\fake\Ordinary Book.pdf", chat_fn=None, user_filter={})
    assert t == "Ordinary Book"


def test_fallback_strips_source():
    """兜底剥离 Anna's Archive 来源后缀。"""
    t, _ = _extract_book_meta_fallback(r"D:\fake\Life -- Anna's Archive.pdf")
    assert "Archive" not in t


# ── R5: 前 15 页提取 ──
def test_first_pages_extract():
    """提取 PDF 前 15 页文本（带页码标记）；非 PDF 返回空。"""
    from paeg_vocabulary.metadata import _extract_first_pages
    t = _extract_first_pages(r"D:\fake\not_a_pdf.pdf", 15)
    assert t == ""
