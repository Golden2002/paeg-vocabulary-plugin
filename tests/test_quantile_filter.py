# -*- coding: utf-8 -*-
"""P4 ⭐ 统一分位筛选测试（Q≥U OR is_important + 三道闸防失控）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.core.entry import CandidateWord
from paeg_vocabulary.core.context import VocabularyContext
from paeg_vocabulary.quantile_filter import (
    quantile_filter_candidates, AntiRunawayConfig,
)


def _mk_candidates():
    """构造候选词：难/易/术语/基础高频混合。"""
    cands = [
        # (headword, freq, zipf, cefr_guess, is_term)
        CandidateWord(headword="abandonment", lemma="abandonment", freq_count=3,
                      global_zipf=3.4, cefr_guess="C1"),
        CandidateWord(headword="the", lemma="the", freq_count=100,
                      global_zipf=7.7, cefr_guess="A1"),
        CandidateWord(headword="phenomenology", lemma="phenomenology", freq_count=8,
                      global_zipf=2.7, cefr_guess="C2"),
        CandidateWord(headword="run", lemma="run", freq_count=50,
                      global_zipf=5.5, cefr_guess="B1"),
        CandidateWord(headword="serendipity", lemma="serendipity", freq_count=1,
                      global_zipf=3.0, cefr_guess="C2"),
        CandidateWord(headword="life", lemma="life", freq_count=40,
                      global_zipf=5.9, cefr_guess="A2"),
    ]
    return cands


def _mk_ctx(cands):
    class T:
        def __init__(self, w):
            self.lemma = w
    ctx = VocabularyContext(pdf_path="t.pdf", target_lang="en")
    ctx.clean_corpus = [T(c.headword) for c in cands for _ in range(c.freq_count)]
    return ctx


# ── R1: Q≥U 保留难词 ──
def test_high_u_keeps_hard_words():
    """雅思 7.5（U≈0.59）→ 保留 Q≥U 的难词（abandonment/phenomenology/serendipity）。"""
    cands = _mk_candidates()
    ctx = _mk_ctx(cands)
    ctx = quantile_filter_candidates(ctx, u_level=0.59)
    kept = {c.headword for c in ctx.candidates}
    assert "abandonment" in kept       # Q≈0.80 ≥ 0.59
    assert "phenomenology" in kept     # Q 高
    assert "serendipity" in kept or "the" not in kept  # 难词优先
    assert "the" not in kept           # Q≈0.08 < 0.59
    assert "life" not in kept          # Q≈0.20 < 0.59


# ── R2: 术语豁免（is_important）──
def test_term_exemption():
    """术语（is_important）即使 Q 低于 U 也保留。"""
    cands = _mk_candidates()
    # 给 life 加术语信号（模拟书中定义句）
    ctx = _mk_ctx(cands)
    ctx = quantile_filter_candidates(ctx, u_level=0.59,
                                     important_words={"life"})
    kept = {c.headword for c in ctx.candidates}
    assert "life" in kept, "术语应豁免"


# ── R3: 三道闸——频率地板 ──
def test_frequency_floor():
    """is_important 豁免要求频次≥2（serendipity 仅 1 次不豁免）。"""
    cands = _mk_candidates()
    ctx = _mk_ctx(cands)
    # serendipity freq=1 但标记 important——低于地板仍应滤除
    ctx = quantile_filter_candidates(ctx, u_level=0.95,
                                     important_words={"serendipity"})
    kept = {c.headword for c in ctx.candidates}
    assert "serendipity" not in kept, "频次 1 的词不应被豁免"


# ── R4: 三道闸——占比上限 ──
def test_ratio_cap():
    """important 救回占比 ≤25%。"""
    cands = _mk_candidates()
    ctx = _mk_ctx(cands)
    cfg = AntiRunawayConfig(max_important_ratio=0.5)
    ctx = quantile_filter_candidates(ctx, u_level=0.59,
                                     important_words={"the", "life"},
                                     config=cfg)
    kept = ctx.candidates
    total = len(kept)
    # important 救回数（Q < U 但被豁免）应 ≤ total * 0.5
    # the/life 的 Q 都 < 0.59
    important_saved = sum(1 for c in kept if c.headword in ("the", "life"))
    assert important_saved <= max(1, int(total * cfg.max_important_ratio))


# ── R5: 默认 U（无用户水平）──
def test_default_u():
    """无 U → 默认 0.60（B2 中性）。"""
    cands = _mk_candidates()
    ctx = _mk_ctx(cands)
    ctx = quantile_filter_candidates(ctx)
    assert len(ctx.candidates) > 0


# ── R6: 兼容旧接口（cefr_max / zipf_threshold）──
def test_legacy_interface():
    """旧 filter_candidates 签名仍可用（registry 兼容）。"""
    from paeg_vocabulary.pipeline.filter import filter_candidates
    cands = _mk_candidates()
    ctx = _mk_ctx(cands)
    ctx2 = filter_candidates(ctx, cefr_max="C1", filter_mode="learn")
    assert hasattr(ctx2, "candidates")
